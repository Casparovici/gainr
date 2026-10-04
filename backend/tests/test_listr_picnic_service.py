from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import config
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.repositories import listr_list_repo, picnic_session_repo
from app.repositories import listr_item_repo
from app.services.listr_picnic_service import (
    ListrPicnicService,
    MissingIngredientCategory,
    PicnicNotConfigured,
    PicnicNotConnected,
    summarize_deliveries,
)
from app.services.picnic_provider import (
    LoginResult,
    PicnicAuthError,
    PicnicCart,
    PicnicCheckout,
    PicnicDelivery,
    PicnicProduct,
    PicnicPromoSection,
    PicnicRecipeDetail,
    PicnicRecipeIngredient,
    PicnicRecipeSummary,
)


def make_item(db, name="Melk", picnic_product_id=None) -> ListrItem:
    category = ListrCategory(name="Zuivel")
    db.add(category)
    db.flush()
    item = ListrItem(name=name, category_id=category.id, default_unit="stuks", picnic_product_id=picnic_product_id)
    db.add(item)
    db.flush()
    return item


def add_line(db, list_id, item, is_checked=False):
    line = listr_list_repo.create_list_item(
        db, list_id=list_id, grocery_item_id=item.id, quantity=Decimal(1), unit=item.default_unit,
        is_checked=is_checked, sort_order=0,
    )
    return line


class FakePicnicClient:
    def __init__(self):
        self.login_result = LoginResult(auth_key="provisional-key", requires_2fa=False)
        self.verify_2fa_result = "real-key"
        self.search_results: list[PicnicProduct] = []
        self.added: list[tuple[str, str, int]] = []  # (auth_key, product_id, count)
        self.raise_auth_error_on_add = False
        self.raise_auth_error_on_search = False
        self.generate_2fa_calls = 0
        self.cookbook: list[PicnicRecipeSummary] = []
        self.recipe_detail = PicnicRecipeDetail(servings=None, ingredients=[], instructions="")
        self.raise_auth_error_on_cookbook = False
        self.raise_auth_error_on_recipe_detail = False
        self.deliveries: list[PicnicDelivery] = []
        self.raise_auth_error_on_deliveries = False
        self.cart = PicnicCart(mts=111, lines=[], total_cents=0, deposit_cents=0, checkout_total_cents=0,
                               selected_slot_id=None, selected_slot_state=None)
        self.checkouts: list[tuple[str, int, str]] = []  # (auth_key, mts, return_url)
        self.raise_auth_error_on_cart = False
        self.promotion_calls = 0

    def login(self, email, password):
        return self.login_result

    def generate_2fa_code(self, provisional_auth_key):
        self.generate_2fa_calls += 1

    def verify_2fa(self, provisional_auth_key, code):
        return self.verify_2fa_result

    def search(self, auth_key, query):
        if self.raise_auth_error_on_search:
            raise PicnicAuthError("expired")
        return self.search_results

    def add_to_cart(self, auth_key, product_id, count=1):
        if self.raise_auth_error_on_add:
            raise PicnicAuthError("expired")
        self.added.append((auth_key, product_id, count))

    def get_cookbook(self, auth_key):
        if self.raise_auth_error_on_cookbook:
            raise PicnicAuthError("expired")
        return self.cookbook

    def get_deliveries(self, auth_key):
        if self.raise_auth_error_on_deliveries:
            raise PicnicAuthError("expired")
        return self.deliveries

    def get_cart(self, auth_key):
        if self.raise_auth_error_on_cart:
            raise PicnicAuthError("expired")
        return self.cart

    def checkout(self, auth_key, mts, return_url):
        self.checkouts.append((auth_key, mts, return_url))
        return PicnicCheckout(order_id="o1", transaction_id="t1", payment_url="https://bank.example/pay")

    def get_promotions(self, auth_key):
        self.promotion_calls += 1
        return [PicnicPromoSection(title="Fruit", products=[])]

    def get_recipe_detail(self, auth_key, recipe_id):
        if self.raise_auth_error_on_recipe_detail:
            raise PicnicAuthError("expired")
        return self.recipe_detail


@pytest.fixture()
def fake():
    return FakePicnicClient()


@pytest.fixture()
def service(fake):
    return ListrPicnicService(provider=fake)


# -- start_login / complete_login ---------------------------------------------------------


def test_start_login_requires_configured_credentials(db_session, service, monkeypatch):
    monkeypatch.setattr(config, "PICNIC_EMAIL", None)
    monkeypatch.setattr(config, "PICNIC_PASSWORD", None)

    with pytest.raises(PicnicNotConfigured):
        service.start_login(db_session)


def test_start_login_without_2fa_stores_the_key_immediately(db_session, service, fake, monkeypatch):
    monkeypatch.setattr(config, "PICNIC_EMAIL", "me@example.com")
    monkeypatch.setattr(config, "PICNIC_PASSWORD", "hunter2")
    fake.login_result = LoginResult(auth_key="final-key", requires_2fa=False)

    requires_2fa = service.start_login(db_session)

    assert requires_2fa is False
    assert picnic_session_repo.get(db_session).auth_key == "final-key"
    assert fake.generate_2fa_calls == 0


def test_start_login_with_2fa_sends_a_code_and_stores_the_provisional_key(db_session, service, fake, monkeypatch):
    monkeypatch.setattr(config, "PICNIC_EMAIL", "me@example.com")
    monkeypatch.setattr(config, "PICNIC_PASSWORD", "hunter2")
    fake.login_result = LoginResult(auth_key="provisional-key", requires_2fa=True)

    requires_2fa = service.start_login(db_session)

    assert requires_2fa is True
    assert fake.generate_2fa_calls == 1
    assert picnic_session_repo.get(db_session).auth_key == "provisional-key"


def test_complete_login_replaces_the_provisional_key_with_the_real_one(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "provisional-key")
    fake.verify_2fa_result = "real-key"

    service.complete_login(db_session, "123456")

    assert picnic_session_repo.get(db_session).auth_key == "real-key"


def test_complete_login_without_a_prior_login_raises(db_session, service):
    with pytest.raises(PicnicNotConnected):
        service.complete_login(db_session, "123456")


# -- search_products ------------------------------------------------------------------------


def test_search_without_a_session_raises(db_session, service):
    with pytest.raises(PicnicNotConnected):
        service.search_products(db_session, "melk")


def test_search_clears_an_expired_session_and_raises(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "stale-key")
    fake.raise_auth_error_on_search = True

    with pytest.raises(PicnicNotConnected):
        service.search_products(db_session, "melk")

    assert picnic_session_repo.get(db_session) is None


# -- push_list_to_cart -----------------------------------------------------------------------


def test_push_skips_unmapped_items_and_reports_them(db_session, service):
    picnic_session_repo.set_auth_key(db_session, "key")
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    unmapped_item = make_item(db_session, "Kaas", picnic_product_id=None)
    line = add_line(db_session, grocery_list.id, unmapped_item)

    result = service.push_list_to_cart(db_session, grocery_list.id)

    assert result.pushed == []
    assert result.unmapped_item_ids == [line.id]


def test_push_adds_mapped_items_to_the_real_cart(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    mapped_item = make_item(db_session, "Melk", picnic_product_id="s123")
    add_line(db_session, grocery_list.id, mapped_item)

    result = service.push_list_to_cart(db_session, grocery_list.id)

    assert result.pushed == ["Melk"]
    assert result.unmapped_item_ids == []
    assert fake.added == [("key", "s123", 1)]


def test_push_excludes_checked_items(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    mapped_item = make_item(db_session, "Melk", picnic_product_id="s123")
    add_line(db_session, grocery_list.id, mapped_item, is_checked=True)

    result = service.push_list_to_cart(db_session, grocery_list.id)

    assert result.pushed == []
    assert fake.added == []


def test_push_without_a_session_raises(db_session, service):
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")

    with pytest.raises(PicnicNotConnected):
        service.push_list_to_cart(db_session, grocery_list.id)


def test_push_clears_an_expired_session_and_raises(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "stale-key")
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    mapped_item = make_item(db_session, "Melk", picnic_product_id="s123")
    add_line(db_session, grocery_list.id, mapped_item)
    fake.raise_auth_error_on_add = True

    with pytest.raises(PicnicNotConnected):
        service.push_list_to_cart(db_session, grocery_list.id)

    assert picnic_session_repo.get(db_session) is None


# -- list_cookbook -----------------------------------------------------------------------------


def test_list_cookbook_without_a_session_raises(db_session, service):
    with pytest.raises(PicnicNotConnected):
        service.list_cookbook(db_session)


def test_list_cookbook_returns_the_providers_recipes(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    fake.cookbook = [PicnicRecipeSummary(id="aaaa1111", name="Pasta", segment="SAVED_RECIPES")]

    assert service.list_cookbook(db_session) == fake.cookbook


def test_list_cookbook_clears_an_expired_session_and_raises(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "stale-key")
    fake.raise_auth_error_on_cookbook = True

    with pytest.raises(PicnicNotConnected):
        service.list_cookbook(db_session)

    assert picnic_session_repo.get(db_session) is None


# -- get_recipe_preview -------------------------------------------------------------------------


def test_preview_marks_an_ingredient_matching_an_existing_item_by_name(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    existing = make_item(db_session, "Melk")
    fake.recipe_detail = PicnicRecipeDetail(
        servings=2, ingredients=[PicnicRecipeIngredient(name="Melk", quantity=Decimal(1), unit="l")], instructions="Doe iets."
    )

    preview = service.get_recipe_preview(db_session, "aaaa1111")

    assert preview.servings == 2
    assert preview.instructions == "Doe iets."
    assert preview.ingredients[0].matched_item_id == existing.id
    assert preview.ingredients[0].matched_item_name == "Melk"


def test_preview_leaves_an_unmatched_ingredient_unmapped(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    fake.recipe_detail = PicnicRecipeDetail(
        servings=None, ingredients=[PicnicRecipeIngredient(name="Kipdijfilets", quantity=Decimal(300), unit="g")], instructions=""
    )

    preview = service.get_recipe_preview(db_session, "aaaa1111")

    assert preview.ingredients[0].matched_item_id is None
    assert preview.ingredients[0].matched_item_name is None


def test_preview_without_a_session_raises(db_session, service):
    with pytest.raises(PicnicNotConnected):
        service.get_recipe_preview(db_session, "aaaa1111")


# -- import_recipe -------------------------------------------------------------------------------


def test_import_reuses_an_existing_item_by_name(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    existing = make_item(db_session, "Melk")
    fake.recipe_detail = PicnicRecipeDetail(
        servings=2, ingredients=[PicnicRecipeIngredient(name="Melk", quantity=Decimal(1), unit="l")], instructions="Doe iets."
    )

    recipe = service.import_recipe(db_session, "aaaa1111", "Ontbijt", [], [None])

    assert recipe.title == "Ontbijt"
    assert recipe.servings == 2
    assert recipe.instructions == "Doe iets."
    assert len(recipe.ingredients) == 1
    assert recipe.ingredients[0].grocery_item_id == existing.id
    assert recipe.ingredients[0].quantity == Decimal(1)
    assert recipe.ingredients[0].unit == "l"


def test_import_creates_a_new_item_with_the_supplied_category(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    category = ListrCategory(name="Vlees & Vis")
    db_session.add(category)
    db_session.flush()
    fake.recipe_detail = PicnicRecipeDetail(
        servings=4,
        ingredients=[PicnicRecipeIngredient(name="Kipdijfilets", quantity=Decimal(300), unit="g")],
        instructions="## Stap 1\n\nBak de kip.",
    )

    recipe = service.import_recipe(db_session, "aaaa1111", "Kip recept", [], [category.id])

    new_item = listr_item_repo.get_by_name(db_session, "Kipdijfilets")
    assert new_item is not None
    assert new_item.category_id == category.id
    assert new_item.default_unit == "g"
    assert recipe.ingredients[0].grocery_item_id == new_item.id


def test_import_raises_when_a_new_ingredient_has_no_category(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    fake.recipe_detail = PicnicRecipeDetail(
        servings=None, ingredients=[PicnicRecipeIngredient(name="Kipdijfilets", quantity=Decimal(300), unit="g")], instructions=""
    )

    with pytest.raises(MissingIngredientCategory):
        service.import_recipe(db_session, "aaaa1111", "Kip recept", [], [None])


def test_import_rejects_a_mismatched_category_list_length(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    fake.recipe_detail = PicnicRecipeDetail(
        servings=None, ingredients=[PicnicRecipeIngredient(name="Melk", quantity=Decimal(1), unit="l")], instructions=""
    )

    with pytest.raises(ValueError):
        service.import_recipe(db_session, "aaaa1111", "Naam", [], [])


def test_import_without_a_session_raises(db_session, service):
    with pytest.raises(PicnicNotConnected):
        service.import_recipe(db_session, "aaaa1111", "Naam", [], [])


# -- order history -------------------------------------------------------------------------------

CEST = timezone(timedelta(hours=2))


def delivery(day: date, cents: int, orders: int = 1, id_: str | None = None) -> PicnicDelivery:
    return PicnicDelivery(
        id=id_ or day.isoformat(), delivered_at=datetime(day.year, day.month, day.day, 15, 0, tzinfo=CEST),
        total_cents=cents, order_count=orders,
    )


def test_order_history_covers_a_rolling_twelve_months_and_buckets_by_calendar_month():
    history = summarize_deliveries(
        [
            delivery(date(2026, 9, 20), 8702, orders=2),
            delivery(date(2026, 9, 9), 8612),
            delivery(date(2025, 10, 3), 5000),  # first day inside the window
            delivery(date(2025, 10, 2), 9999),  # exactly 12 months back -- outside
        ],
        as_of=date(2026, 10, 2),
    )

    assert history.since == date(2025, 10, 3)
    assert history.currency == "EUR"
    assert history.total == Decimal("223.14")
    assert [d.id for d in history.deliveries] == ["2026-09-20", "2026-09-09", "2025-10-03"]  # newest first
    assert history.average_per_delivery == Decimal("223.14") / 3
    # Oct 2025 (partial) through Oct 2026 (partial): 13 calendar months, empty ones included.
    assert [m.month for m in history.months][0] == date(2025, 10, 1)
    assert [m.month for m in history.months][-1] == date(2026, 10, 1)
    assert len(history.months) == 13
    by_month = {m.month: m for m in history.months}
    assert by_month[date(2026, 9, 1)].total == Decimal("173.14")
    assert by_month[date(2026, 9, 1)].deliveries == 2
    assert by_month[date(2025, 10, 1)].total == Decimal("50")
    assert by_month[date(2026, 5, 1)].total == 0


def test_order_history_with_no_deliveries_is_zero_not_an_error():
    history = summarize_deliveries([], as_of=date(2026, 10, 2))

    assert history.total == 0
    assert history.deliveries == []
    assert history.average_per_delivery is None
    assert all(m.total == 0 for m in history.months)


def test_order_history_without_a_session_raises(db_session, service):
    with pytest.raises(PicnicNotConnected):
        service.order_history(db_session)


def test_order_history_reads_the_providers_deliveries(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    fake.deliveries = [delivery(date(2026, 9, 20), 8702)]

    history = service.order_history(db_session, as_of=date(2026, 10, 2))

    assert history.total == Decimal("87.02")


def test_order_history_clears_an_expired_session_and_raises(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "stale-key")
    fake.raise_auth_error_on_deliveries = True

    with pytest.raises(PicnicNotConnected):
        service.order_history(db_session)

    assert picnic_session_repo.get(db_session) is None


# -- prices ------------------------------------------------------------------------------------


def test_refresh_prices_updates_linked_items_from_the_matching_search_result(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    category = ListrCategory(name="Diversen")
    db_session.add(category)
    db_session.flush()
    bananas = ListrItem(name="Bananen", category_id=category.id, default_unit="kg",
                        picnic_product_id="s1018276", picnic_product_name="Chiquita bananen")
    gone = ListrItem(name="Oude kaas", category_id=category.id, default_unit="stuks", picnic_product_id="s0000001")
    milk = ListrItem(name="Melk", category_id=category.id, default_unit="liter")  # not linked -- never searched
    db_session.add_all([bananas, gone, milk])
    db_session.flush()
    fake.search_results = [
        PicnicProduct(id="s1018231", name="Bananen", unit_quantity="5 stuks", display_price=119),
        PicnicProduct(id="s1018276", name="Chiquita bananen", unit_quantity="1 kilo", display_price=229, image_id="b9dc"),
    ]

    updated, not_found = service.refresh_prices(db_session)

    assert (updated, not_found) == (1, ["Oude kaas"])
    assert bananas.picnic_price == Decimal("2.29")
    assert bananas.picnic_unit_quantity == "1 kilo"
    assert bananas.picnic_price_at is not None
    assert bananas.picnic_image_id == "b9dc"
    assert gone.picnic_price is None


def test_refresh_prices_without_a_session_raises(db_session, service):
    with pytest.raises(PicnicNotConnected):
        service.refresh_prices(db_session)



# -- ordering ----------------------------------------------------------------------------------


def test_checkout_quotes_the_cart_version_the_reader_saw(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")

    checkout = service.checkout(db_session, mts=1790921779016, return_url="https://example.test/listr/winkelwagen")

    assert fake.checkouts == [("key", 1790921779016, "https://example.test/listr/winkelwagen")]
    assert checkout.payment_url == "https://bank.example/pay"


def test_checkout_without_a_session_raises_and_never_calls_picnic(db_session, service, fake):
    with pytest.raises(PicnicNotConnected):
        service.checkout(db_session, mts=1, return_url="https://example.test/")
    assert fake.checkouts == []


def test_cart_clears_an_expired_session_and_raises(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "stale-key")
    fake.raise_auth_error_on_cart = True

    with pytest.raises(PicnicNotConnected):
        service.get_cart(db_session)

    assert picnic_session_repo.get(db_session) is None



def test_promotions_are_fetched_at_most_once_per_day(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    morning = datetime(2026, 10, 2, 8, 0)

    service.promotions(db_session, now=morning)
    service.promotions(db_session, now=morning.replace(hour=23, minute=59))
    assert fake.promotion_calls == 1

    service.promotions(db_session, now=morning + timedelta(days=1))
    assert fake.promotion_calls == 2


def test_an_empty_promotions_result_is_not_kept(db_session, service, fake):
    picnic_session_repo.set_auth_key(db_session, "key")
    fake.get_promotions = lambda auth_key: (setattr(fake, "promotion_calls", fake.promotion_calls + 1), [])[1]
    noon = datetime(2026, 10, 2, 12, 0)

    service.promotions(db_session, now=noon)
    service.promotions(db_session, now=noon.replace(minute=5))

    assert fake.promotion_calls == 2
