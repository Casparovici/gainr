"""What "connect to Picnic" and "push a list" actually mean for listr's own data --
picnic_provider.py only knows how to talk to Picnic's API. See
docs/adr/0011-listr-picnic-integration.md.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app import config
from app.models.listr_recipe import ListrRecipe
from app.repositories import listr_item_repo, listr_list_repo, listr_recipe_category_repo, listr_recipe_repo, picnic_session_repo
from app.services.picnic_provider import (
    PicnicAuthError,
    PicnicCart,
    PicnicCheckout,
    PicnicDelivery,
    PicnicProduct,
    PicnicPromoSection,
    PicnicProvider,
    PicnicRecipeSummary,
    PicnicSlot,
    picnic_provider,
)


class PicnicNotConfigured(Exception):
    """GAINR_PICNIC_EMAIL/GAINR_PICNIC_PASSWORD aren't set in the environment."""


class PicnicNotConnected(Exception):
    """No valid session yet (or it just expired) -- the reader needs to log in again."""


class MissingIngredientCategory(Exception):
    """An ingredient that doesn't match an existing catalog item was imported without a
    category to file its new ListrItem under."""

    def __init__(self, ingredient_name: str):
        self.ingredient_name = ingredient_name
        super().__init__(f"No category given for new ingredient {ingredient_name!r}")


@dataclass
class PushResult:
    pushed: list[str] = field(default_factory=list)  # grocery item names added to the cart
    unmapped_item_ids: list[int] = field(default_factory=list)  # list-item ids needing a Picnic product picked


@dataclass
class RecipeIngredientPreview:
    name: str
    quantity: Decimal
    unit: str
    # Set when an existing ListrItem already has this exact name -- reused silently on
    # import. None means importing this ingredient will create a new catalog item, which needs
    # a category (see MissingIngredientCategory).
    matched_item_id: int | None
    matched_item_name: str | None


@dataclass
class RecipePreview:
    servings: int | None
    instructions: str
    ingredients: list[RecipeIngredientPreview] = field(default_factory=list)


# Picnic only delivers in euros (NL/DE/FR/BE); `total_cents` is always EUR cents.
PICNIC_CURRENCY = "EUR"
ORDER_HISTORY_MONTHS = 12


@dataclass
class PicnicMonthSpend:
    month: date  # first day of the calendar month
    total: Decimal
    deliveries: int


@dataclass
class PicnicOrderHistory:
    since: date  # first day inside the window
    currency: str
    total: Decimal
    deliveries: list[PicnicDelivery]  # newest first, only those inside the window
    # Oldest first, every calendar month the window touches (zero if nothing was delivered) --
    # so the first and last month are usually partial; see summarize_deliveries.
    months: list[PicnicMonthSpend]

    @property
    def average_per_delivery(self) -> Decimal | None:
        return self.total / len(self.deliveries) if self.deliveries else None


def summarize_deliveries(
    deliveries: list[PicnicDelivery], as_of: date, months: int = ORDER_HISTORY_MONTHS
) -> PicnicOrderHistory:
    """The deliveries of the last `months` months up to and including `as_of` -- a rolling
    window (3 Oct 2025 - 2 Oct 2026), so the total really is "the last 12 months" whatever day
    of the month it's asked. The per-month breakdown buckets those same deliveries by calendar
    month, which means the oldest and the current month only cover part of a month."""
    since = as_of - relativedelta(months=months) + timedelta(days=1)
    inside = [d for d in deliveries if since <= d.delivered_at.date() <= as_of]
    first_month, last_month = since.replace(day=1), as_of.replace(day=1)
    buckets: dict[date, PicnicMonthSpend] = {}
    month = first_month
    while month <= last_month:
        buckets[month] = PicnicMonthSpend(month, Decimal(0), 0)
        month += relativedelta(months=1)
    for d in inside:
        bucket = buckets[d.delivered_at.date().replace(day=1)]
        bucket.total += Decimal(d.total_cents) / 100
        bucket.deliveries += 1
    return PicnicOrderHistory(
        since=since,
        currency=PICNIC_CURRENCY,
        total=sum((Decimal(d.total_cents) for d in inside), Decimal(0)) / 100,
        deliveries=sorted(inside, key=lambda d: d.delivered_at, reverse=True),
        months=list(buckets.values()),
    )


class ListrPicnicService:
    def __init__(self, provider: PicnicProvider | None = None):
        self.provider = provider or picnic_provider
        self._promotions: tuple[datetime, list[PicnicPromoSection]] | None = None

    def is_connected(self, db: Session) -> bool:
        return picnic_session_repo.get(db) is not None

    def start_login(self, db: Session) -> bool:
        """Returns True if a 2FA code was just sent and complete_login is needed next; False if
        login succeeded outright and the session is already usable."""
        if not config.PICNIC_EMAIL or not config.PICNIC_PASSWORD:
            raise PicnicNotConfigured()
        result = self.provider.login(config.PICNIC_EMAIL, config.PICNIC_PASSWORD)
        # Stored either way: a provisional key is exactly what verify_2fa needs next, and
        # complete_login reads whatever's currently here rather than threading it through the API.
        picnic_session_repo.set_auth_key(db, result.auth_key)
        if result.requires_2fa:
            self.provider.generate_2fa_code(result.auth_key)
            return True
        return False

    def complete_login(self, db: Session, code: str) -> None:
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        auth_key = self.provider.verify_2fa(session.auth_key, code)
        picnic_session_repo.set_auth_key(db, auth_key)

    def search_products(self, db: Session, query: str) -> list[PicnicProduct]:
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        try:
            return self.provider.search(session.auth_key, query)
        except PicnicAuthError:
            picnic_session_repo.clear(db)
            raise PicnicNotConnected()

    def push_list_to_cart(self, db: Session, list_id: int) -> PushResult:
        """Every unchecked line whose grocery item already has a picnic_product_id gets added
        to the real Picnic cart, always as count 1 -- Picnic's cart counts a specific product,
        not a weight/volume, so a listr quantity like "500 gram" can't be mechanically turned
        into "how many bags" without guessing (see the ADR). Lines with no mapping yet are
        reported back rather than silently skipped, so the caller can prompt for one."""
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()

        result = PushResult()
        for line in listr_list_repo.list_items(db, list_id):
            if line.is_checked:
                continue
            product_id = line.grocery_item.picnic_product_id
            if product_id is None:
                result.unmapped_item_ids.append(line.id)
                continue
            try:
                self.provider.add_to_cart(session.auth_key, product_id, count=1)
            except PicnicAuthError:
                picnic_session_repo.clear(db)
                raise PicnicNotConnected()
            result.pushed.append(line.grocery_item.name)
        return result

    def fetch_deliveries(self, db: Session) -> list[PicnicDelivery]:
        """The account's whole completed-delivery history, read live (one call)."""
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        try:
            return self.provider.get_deliveries(session.auth_key)
        except PicnicAuthError:
            picnic_session_repo.clear(db)
            raise PicnicNotConnected()

    def order_history(
        self, db: Session, as_of: date | None = None, deliveries: list[PicnicDelivery] | None = None
    ) -> PicnicOrderHistory:
        """What the account spent on Picnic over the last ORDER_HISTORY_MONTHS months -- from
        `deliveries` when the caller already fetched them, otherwise read live."""
        if deliveries is None:
            deliveries = self.fetch_deliveries(db)
        return summarize_deliveries(deliveries, as_of or date.today())

    def refresh_prices(self, db: Session) -> tuple[int, list[str]]:
        """Re-reads the current price of every catalog item linked to a Picnic product, by
        searching Picnic for the product's name and taking the result with the same id (search
        results carry a clean price and unit; the product page only has them inside display
        markup). Returns how many were updated and the names Picnic no longer returns -- those
        keep their last known price. One search per product, so this is for a daily job or an
        explicit "update prices", not a page load."""
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        updated, not_found = 0, []
        now = datetime.now()
        for item in listr_item_repo.list_picnic_mapped(db):
            try:
                results = self.provider.search(session.auth_key, item.picnic_product_name or item.name)
            except PicnicAuthError:
                picnic_session_repo.clear(db)
                raise PicnicNotConnected()
            match = next((r for r in results if r.id == item.picnic_product_id), None)
            if match is None or match.display_price is None:
                not_found.append(item.name)
                continue
            listr_item_repo.update_item(
                db, item,
                picnic_price=Decimal(match.display_price) / 100,
                picnic_unit_quantity=match.unit_quantity or None,
                picnic_price_at=now,
                picnic_image_id=match.image_id or item.picnic_image_id,
            )
            updated += 1
        return updated, not_found

    # -- cart, delivery slot and ordering (ADR 0028) ------------------------------------------

    def _call(self, db: Session, fn):
        """Runs `fn(auth_key)` against the stored session, clearing it if Picnic rejects it."""
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        try:
            return fn(session.auth_key)
        except PicnicAuthError:
            picnic_session_repo.clear(db)
            raise PicnicNotConnected()

    def get_cart(self, db: Session) -> PicnicCart:
        return self._call(db, self.provider.get_cart)

    def add_to_cart(self, db: Session, product_id: str, count: int = 1) -> PicnicCart:
        def add(key: str) -> PicnicCart:
            self.provider.add_to_cart(key, product_id, count)
            return self.provider.get_cart(key)

        return self._call(db, add)

    def remove_from_cart(self, db: Session, product_id: str, count: int = 1) -> PicnicCart:
        return self._call(db, lambda key: self.provider.remove_from_cart(key, product_id, count))

    def delivery_slots(self, db: Session) -> list[PicnicSlot]:
        return self._call(db, self.provider.get_delivery_slots)

    def set_delivery_slot(self, db: Session, slot_id: str) -> PicnicCart:
        return self._call(db, lambda key: self.provider.set_delivery_slot(key, slot_id))

    def checkout(self, db: Session, mts: int, return_url: str) -> PicnicCheckout:
        """Places the cart as an order -- pending until the reader approves the payment in their
        bank app. `mts` is the cart version the reader was looking at when they pressed order:
        Picnic refuses a checkout for any other version, so an order is never started for a
        cart that changed since (on the phone, in the Picnic app) without them seeing it."""
        return self._call(db, lambda key: self.provider.checkout(key, mts, return_url))

    def promotions(self, db: Session, now: datetime | None = None) -> list[PicnicPromoSection]:
        """The products on offer, grouped as Picnic's own Aanbiedingen tab does. Fetched at most
        once per calendar day: offers run for a week, and the page is ~3 MB. An empty result
        isn't kept, so a hiccup on Picnic's side (or a page we couldn't read) is retried on the
        next visit instead of leaving the day without offers. Held in memory, so a restart
        (a deploy) costs one extra fetch that day."""
        now = now or datetime.now()
        if self._promotions is not None and self._promotions[0].date() == now.date():
            return self._promotions[1]
        sections = self._call(db, self.provider.get_promotions)
        self._promotions = (now, sections) if sections else None
        return sections

    def checkout_status(self, db: Session, transaction_id: str) -> str:
        return self._call(db, lambda key: self.provider.checkout_status(key, transaction_id))

    def cancel_checkout(self, db: Session, transaction_id: str) -> None:
        self._call(db, lambda key: self.provider.cancel_checkout(key, transaction_id))

    def list_cookbook(self, db: Session) -> list[PicnicRecipeSummary]:
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        try:
            return self.provider.get_cookbook(session.auth_key)
        except PicnicAuthError:
            picnic_session_repo.clear(db)
            raise PicnicNotConnected()

    def get_recipe_preview(self, db: Session, recipe_id: str) -> RecipePreview:
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        try:
            detail = self.provider.get_recipe_detail(session.auth_key, recipe_id)
        except PicnicAuthError:
            picnic_session_repo.clear(db)
            raise PicnicNotConnected()

        ingredients = []
        for ingredient in detail.ingredients:
            existing = listr_item_repo.get_by_name(db, ingredient.name)
            ingredients.append(
                RecipeIngredientPreview(
                    name=ingredient.name,
                    quantity=ingredient.quantity,
                    unit=ingredient.unit,
                    matched_item_id=existing.id if existing else None,
                    matched_item_name=existing.name if existing else None,
                )
            )
        return RecipePreview(servings=detail.servings, instructions=detail.instructions, ingredients=ingredients)

    def import_recipe(
        self,
        db: Session,
        recipe_id: str,
        name: str,
        recipe_category_ids: list[int],
        ingredient_category_ids: list[int | None],
    ) -> ListrRecipe:
        """Re-fetches the recipe fresh from Picnic rather than trusting a client-held preview --
        Picnic is the source of truth. `ingredient_category_ids` must be the same length and
        order as the ingredients this fetch returns (the same order the preview endpoint already
        returned them in, moments earlier) -- entries only matter for ingredients that don't
        already match an existing catalog item by name."""
        session = picnic_session_repo.get(db)
        if session is None:
            raise PicnicNotConnected()
        try:
            detail = self.provider.get_recipe_detail(session.auth_key, recipe_id)
        except PicnicAuthError:
            picnic_session_repo.clear(db)
            raise PicnicNotConnected()

        if len(ingredient_category_ids) != len(detail.ingredients):
            raise ValueError(
                f"Expected {len(detail.ingredients)} ingredient_category_ids, got {len(ingredient_category_ids)}"
            )

        categories = listr_recipe_category_repo.get_by_ids(db, recipe_category_ids)
        recipe = listr_recipe_repo.create_recipe(
            db, title=name, servings=detail.servings, instructions=detail.instructions, notes=None, categories=categories,
        )
        for index, ingredient in enumerate(detail.ingredients):
            item = listr_item_repo.get_by_name(db, ingredient.name)
            if item is None:
                category_id = ingredient_category_ids[index]
                if category_id is None:
                    raise MissingIngredientCategory(ingredient.name)
                item = listr_item_repo.create_item(
                    db, name=ingredient.name, category_id=category_id, default_unit=ingredient.unit or "stuks",
                )
            listr_recipe_repo.add_ingredient(
                db,
                recipe_id=recipe.id,
                grocery_item_id=item.id,
                quantity=ingredient.quantity,
                unit=ingredient.unit or item.default_unit,
                sort_order=index,
            )
        return listr_recipe_repo.get_recipe(db, recipe.id)


listr_picnic_service = ListrPicnicService()
