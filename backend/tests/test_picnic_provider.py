from decimal import Decimal

from datetime import datetime, timedelta, timezone

from app.services.picnic_provider import (
    _parse_cart,
    _parse_deliveries,
    _parse_promo_page,
    _parse_slots,
    picnic_image_url,
    PicnicProduct,
    PicnicRecipeSummary,
    _collect_instructions_tab_text,
    _extract_recipe_tiles,
    _extract_selling_units,
    _find_by_id,
    _parse_instructions_tab,
)


def test_extracts_a_selling_unit_nested_inside_a_fusion_page_tree():
    page = {
        "body": {
            "child": {
                "type": "SELLING_UNIT_TILE",
                "sellingUnit": {
                    "id": "s123",
                    "name": "Halfvolle melk",
                    "unit_quantity": "1 l",
                    "display_price": 129,
                },
            }
        }
    }

    result = _extract_selling_units(page)

    assert result == [PicnicProduct(id="s123", name="Halfvolle melk", unit_quantity="1 l", display_price=129)]


def test_extracts_multiple_selling_units_from_a_list_of_tiles():
    page = {
        "items": [
            {"type": "SELLING_UNIT_TILE", "sellingUnit": {"id": "s1", "name": "A", "unit_quantity": "1 stuk"}},
            {"type": "SOMETHING_ELSE", "irrelevant": True},
            {"type": "SELLING_UNIT_TILE", "sellingUnit": {"id": "s2", "name": "B", "unit_quantity": "2 stuks"}},
        ]
    }

    result = _extract_selling_units(page)

    assert {p.id for p in result} == {"s1", "s2"}


def test_deduplicates_the_same_product_appearing_in_more_than_one_tile():
    page = {
        "items": [
            {"sellingUnit": {"id": "s1", "name": "A", "unit_quantity": "1 stuk"}},
            {"sellingUnit": {"id": "s1", "name": "A", "unit_quantity": "1 stuk"}},
        ]
    }

    result = _extract_selling_units(page)

    assert len(result) == 1


def test_ignores_a_selling_unit_with_no_id():
    page = {"sellingUnit": {"name": "no id here"}}

    assert _extract_selling_units(page) == []


def test_returns_empty_list_for_a_page_with_no_selling_units():
    assert _extract_selling_units({"body": {"text": "no products here"}}) == []


# -- _extract_recipe_tiles -------------------------------------------------------------------


def _recipe_tile(recipe_id: str, name: str) -> dict:
    return {
        "type": "TOUCHABLE",
        "onPress": {"actionType": "OPEN", "target": f"app.picnic://store/page;id=selling-group-details-page,selling_group_id={recipe_id}"},
        "onLongPress": {"actionType": "OPEN", "target": f"app.picnic://store/page;id=action-bottom-sheet,id={recipe_id}&name={name}&source=SELLING_GROUP_TILE"},
    }


def test_extracts_a_recipe_tile_with_its_segment():
    page = {
        "analytics": {"contexts": [{"data": {"segment_type": "SAVED_RECIPES"}}]},
        "tile": _recipe_tile("6a1ee3d38d45fb1080af78db", "Thaise%20sat%C3%A9%20bowl"),
    }

    result = _extract_recipe_tiles(page)

    assert result == [PicnicRecipeSummary(id="6a1ee3d38d45fb1080af78db", name="Thaise saté bowl", segment="SAVED_RECIPES")]


def test_recipe_tiles_in_different_segments_are_tagged_independently():
    page = {
        "saved": {
            "analytics": {"contexts": [{"data": {"segment_type": "SAVED_RECIPES"}}]},
            "tile": _recipe_tile("aaaa1111", "Een"),
        },
        "featured": {
            "analytics": {"contexts": [{"data": {"segment_type": "THIS_WEEK_RECIPES"}}]},
            "tile": _recipe_tile("bbbb2222", "Twee"),
        },
    }

    result = {r.id: r.segment for r in _extract_recipe_tiles(page)}

    assert result == {"aaaa1111": "SAVED_RECIPES", "bbbb2222": "THIS_WEEK_RECIPES"}


def test_deduplicates_a_recipe_tile_appearing_in_more_than_one_segment():
    page = {"items": [_recipe_tile("aaaa1111", "Een"), _recipe_tile("aaaa1111", "Een")]}

    assert len(_extract_recipe_tiles(page)) == 1


def test_a_tile_with_no_onLongPress_still_yields_a_recipe_with_an_empty_name():
    page = {"tile": {"type": "TOUCHABLE", "onPress": {"target": "...selling_group_id=aaaa1111"}}}

    result = _extract_recipe_tiles(page)

    assert result == [PicnicRecipeSummary(id="aaaa1111", name="", segment=None)]


def test_a_dict_valued_id_field_does_not_crash_recipe_tile_extraction():
    # Some Fusion nodes use an EXPRESSION object as their "id" rather than a plain string --
    # _extract_recipe_tiles doesn't key off "id" itself, but shares tree-walking territory with
    # _find_by_id below, which must tolerate this.
    page = {"id": {"type": "EXPRESSION", "expression": "..."}, "tile": _recipe_tile("aaaa1111", "Een")}

    assert len(_extract_recipe_tiles(page)) == 1


# -- _find_by_id / _collect_instructions_tab_text ---------------------------------------------


def test_find_by_id_locates_a_nested_node():
    page = {"a": {"b": [{"id": "target", "value": 1}, {"id": "other"}]}}

    found = _find_by_id(page, "target")

    assert found == {"id": "target", "value": 1}


def test_find_by_id_tolerates_a_dict_valued_id_field():
    page = {"id": {"type": "EXPRESSION"}, "child": {"id": "target"}}

    assert _find_by_id(page, "target") == {"id": "target"}


def test_find_by_id_returns_none_when_absent():
    assert _find_by_id({"a": {"b": 1}}, "missing") is None


def test_collect_instructions_tab_text_gathers_markdown_in_order_within_that_node_only():
    page = {
        "instructions_tab": {
            "id": "selling-group-tab-instructions",
            "children": [{"markdown": "Ingrediënten"}, {"markdown": "**Melk** 1 l"}],
        },
        # A true sibling elsewhere in the page -- must not leak into the instructions tab's
        # collected text just because it shares the same overall tree.
        "ingredients_tab": {
            "id": "selling-group-tab-ingredients",
            "children": [{"markdown": "should not appear"}],
        },
    }

    assert _collect_instructions_tab_text(page) == ["Ingrediënten", "**Melk** 1 l"]


def test_collect_instructions_tab_text_is_empty_when_the_node_is_missing():
    assert _collect_instructions_tab_text({"a": 1}) == []


# -- _parse_instructions_tab ------------------------------------------------------------------


def test_parses_ingredient_lines_servings_and_steps():
    texts = [
        "Ingrediënten",
        "**Kipdijfilets** 300 g",
        "**Rode currypasta** 2.25 el",
        "Bereidingswijze",
        "4 porties",
        "**Let op:** dit is de originele bereidingswijze voor 4 porties",
        "Stap 1",
        "Breng een pan met water aan de kook.",
        "Stap 2",
        "Bak de kip.",
        "Tip",
        "Laat de rode peper weg voor een mildere smaak.",
        "Notitie",
        "Voeg toe...",
    ]

    result = _parse_instructions_tab(texts)

    assert result.servings == 4
    assert result.ingredients == [
        _ing("Kipdijfilets", "300", "g"),
        _ing("Rode currypasta", "2.25", "el"),
    ]
    assert result.instructions == (
        "# Stap 1\n\nBreng een pan met water aan de kook.\n\n"
        "# Stap 2\n\nBak de kip.\n\n"
        "# Tip\n\nLaat de rode peper weg voor een mildere smaak."
    )


def test_pantry_staples_catchall_line_is_kept_as_one_freeform_ingredient():
    texts = ["Ingrediënten", "**Uit eigen keuken:** 1.5 teentjes knoflook en 0.75 el zonnebloemolie", "Bereidingswijze"]

    result = _parse_instructions_tab(texts)

    assert result.ingredients == [_ing("1.5 teentjes knoflook en 0.75 el zonnebloemolie", "1", "")]


def test_an_ingredient_line_matching_no_pattern_is_kept_verbatim_rather_than_dropped():
    texts = ["Ingrediënten", "Zout en peper naar smaak", "Bereidingswijze"]

    result = _parse_instructions_tab(texts)

    assert result.ingredients == [_ing("Zout en peper naar smaak", "1", "")]


def test_comma_decimal_quantities_are_parsed():
    texts = ["Ingrediënten", "**Room** 1,5 dl", "Bereidingswijze"]

    result = _parse_instructions_tab(texts)

    assert result.ingredients[0].quantity == Decimal("1.5")


def test_no_servings_line_leaves_servings_none():
    texts = ["Ingrediënten", "**Melk** 1 l", "Bereidingswijze", "Stap 1", "Doe iets."]

    assert _parse_instructions_tab(texts).servings is None


def _ing(name: str, quantity: str, unit: str):
    from app.services.picnic_provider import PicnicRecipeIngredient

    return PicnicRecipeIngredient(name=name, quantity=Decimal(quantity), unit=unit)


def test_parse_deliveries_sums_completed_orders_and_prefers_the_actual_drop_off_time():
    raw = [
        {
            "delivery_id": "rtru3ioniq",
            "creation_time": "2026-09-19T19:49:47.264+02:00",
            "slot": {"window_start": "2026-09-20T14:30:00.000+02:00"},
            "status": "COMPLETED",
            "delivery_time": {"start": "2026-09-20T15:27:11.223+02:00"},
            "orders": [
                {"id": "a", "total_price": 7832, "status": "COMPLETED", "cancellation_time": None},
                {"id": "b", "total_price": 870, "status": "COMPLETED", "cancellation_time": None},
                {"id": "c", "total_price": 500, "status": "CANCELLED", "cancellation_time": "2026-09-19T22:00:00+02:00"},
            ],
        },
        {
            "delivery_id": "older",
            "creation_time": "2026-09-01T10:00:00+02:00",
            "slot": {"window_start": "2026-09-02T18:00:00.000+02:00"},  # no drop-off time
            "status": "COMPLETED",
            "orders": [{"id": "d", "total_price": 4000, "status": "COMPLETED", "cancellation_time": None}],
        },
    ]

    deliveries = _parse_deliveries(raw)

    assert [d.id for d in deliveries] == ["rtru3ioniq", "older"]
    assert deliveries[0].total_cents == 8702  # the cancelled order doesn't count
    assert deliveries[0].order_count == 2
    assert deliveries[0].delivered_at == datetime(2026, 9, 20, 15, 27, 11, 223000, tzinfo=timezone(timedelta(hours=2)))
    assert deliveries[1].delivered_at.date().isoformat() == "2026-09-02"


def test_parse_deliveries_drops_entries_without_completed_orders_or_a_date():
    raw = [
        {"delivery_id": "x", "status": "CANCELLED", "creation_time": "2026-09-01T10:00:00+02:00",
         "orders": [{"total_price": 100, "status": "COMPLETED"}]},
        {"delivery_id": "y", "status": "COMPLETED", "creation_time": "2026-09-01T10:00:00+02:00", "orders": []},
        {"delivery_id": "z", "status": "COMPLETED", "orders": [{"total_price": 100, "status": "COMPLETED"}]},
        "not a dict",
    ]

    assert _parse_deliveries(raw) == []
    assert _parse_deliveries({"error": "unexpected shape"}) == []



def test_parse_cart_reads_counts_bundle_prices_images_and_the_slot_state():
    raw = {
        "mts": 1790921779016,
        "total_price": 4622, "checkout_total_price": 4661, "total_deposit": 39,
        "selected_slot": {"slot_id": "slot-1", "state": "IMPLICIT"},
        "items": [
            {
                "type": "ORDER_LINE", "display_price": 1227, "price": 1227,
                "decorators": [{"type": "PROMO", "text": "BundelBonus"}, {"type": "PRICE", "display_price": 1167}],
                "items": [{
                    "type": "ORDER_ARTICLE", "id": "s1009999", "name": "Zaanse mayonaise", "unit_quantity": "650 ml",
                    "image_ids": ["affe"], "decorators": [{"type": "QUANTITY", "quantity": 3}],
                }],
            },
            {
                "type": "ORDER_LINE", "display_price": 129,
                "items": [{"type": "ORDER_ARTICLE", "id": "s1", "name": "Zonnebloemolie", "unit_quantity": "1 liter"}],
            },
            {"type": "ORDER_LINE", "items": []},
        ],
    }

    cart = _parse_cart(raw)

    assert cart.mts == 1790921779016
    assert (cart.total_cents, cart.checkout_total_cents, cart.deposit_cents) == (4622, 4661, 39)
    assert (cart.selected_slot_id, cart.selected_slot_state) == ("slot-1", "IMPLICIT")
    assert [(l.product_id, l.count, l.price_cents, l.image_id) for l in cart.lines] == [
        ("s1009999", 3, 1167, "affe"),  # the bundle price, not 3 x 409
        ("s1", 1, 129, None),
    ]


def test_parse_slots_sorts_and_skips_entries_without_times():
    raw = [
        {"slot_id": "b", "window_start": "2026-10-03T10:45:00.000+02:00", "window_end": "2026-10-03T11:45:00.000+02:00",
         "cut_off_time": "2026-10-02T13:00:00.000+02:00", "is_available": True, "selected": False, "minimum_order_value": 3500},
        {"slot_id": "a", "window_start": "2026-10-03T08:00:00.000+02:00", "window_end": "2026-10-03T09:00:00.000+02:00",
         "cut_off_time": "2026-10-02T13:00:00.000+02:00", "is_available": False, "unavailability_reason": "OUT_OF_CAPACITY"},
        {"slot_id": "broken"},
    ]

    slots = _parse_slots(raw)

    assert [s.id for s in slots] == ["a", "b"]
    assert slots[0].unavailable_reason == "OUT_OF_CAPACITY" and not slots[0].is_available
    assert slots[1].minimum_order_cents == 3500


def test_picnic_image_url_is_the_public_static_path():
    assert picnic_image_url("affe") == "https://storefront-prod.nl.picnicinternational.com/static/images/affe/small.png"



def _promo_tile(product_id, name, price, label, strike=None):
    data = {"promotion_id": "p-" + product_id, "promotion_label": label, "price": price,
            "show_strikethrough_price": strike is not None}
    if strike is not None:
        data["strikethrough_price"] = float(strike)
    return {
        "type": "PML",
        "analytics": {"contexts": [{"type": "x", "data": {}}, {"type": "promotion", "data": data}]},
        "children": [{"content": {"sellingUnit": {"id": product_id, "name": name, "unit_quantity": "1 st",
                                                  "display_price": price, "image_id": "img-" + product_id}}}],
    }


def test_parse_promo_page_groups_offers_by_section_with_labels_and_old_prices():
    page = {"layout": {"body": {"child": {"child": {"children": [
        {"type": "BLOCK", "id": "campaign-header-tab-bars", "children": [{"type": "PML", "markdown": "Fruit"}]},
        {"type": "BLOCK", "id": "campaign-page-layout-content", "children": [
            {"type": "PML", "id": "marker"},
            {"type": "BLOCK", "id": "campaign-promo-section-1", "children": [
                {"type": "PML", "pml": {"component": {"markdown": "#(#333333)Fruit#(#333333)"}}},
                _promo_tile("s1", "Conference peertjes", 167, "20% korting", strike=209),
                _promo_tile("s2", "Bananen", 119, "#(#ff0000)1+1 gratis#(#ff0000)"),
                _promo_tile("s1", "Conference peertjes", 167, "20% korting", strike=209),  # repeated tile
            ]},
            {"type": "BLOCK", "id": "campaign-promo-section-2", "children": [
                {"type": "PML", "pml": {"component": {"markdown": "Leeg"}}},
            ]},
        ]},
    ]}}}}}

    sections = _parse_promo_page(page)

    assert [s.title for s in sections] == ["Fruit"]  # the empty section is left out
    fruit = sections[0].products
    assert [(p.product.id, p.label, p.product.display_price, p.original_price, p.product.image_id) for p in fruit] == [
        ("s1", "20% korting", 167, 209, "img-s1"),
        ("s2", "1+1 gratis", 119, None, "img-s2"),
    ]


def test_parse_promo_page_tolerates_an_unexpected_shape():
    assert _parse_promo_page({"layout": {}}) == []
    assert _parse_promo_page("not a page") == []
