"""Client for Picnic (Dutch grocery delivery). Picnic has no official public API -- every
endpoint here is the same private, undocumented app API the open-source community wrappers
(`picnic-api` on npm, `python-picnic-api` on PyPI) reverse-engineered from Picnic's own Android
app. Not affiliated with Picnic; see docs/adr/0011-listr-picnic-integration.md for why this is
a small hand-rolled client rather than either of those packages.

Every method takes the auth key as a plain argument rather than storing session state on the
instance, the same statelessness `YFinanceProvider`/`YFinanceFundamentalsProvider` already use
for their external calls -- callers (listr_picnic_service) own persisting it between calls.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from urllib.parse import unquote

import httpx

BASE_URL = "https://storefront-prod.nl.picnicinternational.com/api/15"
# Identifies the calling app version/device to Picnic's API -- the same well-tested default
# values the open-source picnic-api wrapper ships, not invented ones.
USER_AGENT = "okhttp/4.9.0"
PICNIC_AGENT = "30100;1.236.1-15553;"
PICNIC_DEVICE_ID = "3C417201548B2E3B"
CLIENT_ID = 30100

TIMEOUT = 15.0


class PicnicAuthError(Exception):
    """A login, 2FA verification, or an already-stored session key was rejected -- callers
    should surface "reconnect to Picnic", never retry silently or treat it as a bare HTTP error."""


@dataclass
class LoginResult:
    auth_key: str
    # When true, `auth_key` is provisional: it authorizes generate_2fa_code/verify_2fa only,
    # not search/cart calls, until verify_2fa returns the real key.
    requires_2fa: bool


@dataclass
class PicnicProduct:
    id: str
    name: str
    unit_quantity: str  # Picnic's own display string, e.g. "500 g" or "6 stuks"
    display_price: int | None = None  # cents
    # Picnic's image id; the picture itself is public at picnic_image_url(image_id).
    image_id: str | None = None


@dataclass
class PicnicRecipeSummary:
    id: str
    name: str
    # Which cookbook section this tile came from -- SAVED_RECIPES, USER_DEFINED_RECIPES,
    # THIS_WEEK_RECIPES, or another value Picnic adds later. None if it couldn't be determined.
    segment: str | None = None


@dataclass
class PicnicRecipeIngredient:
    name: str
    # Real-world amount (e.g. 300 for "300 g"), not a selling-unit count -- see the module
    # docstring note on why this comes from the instructions tab, not the structured endpoint.
    quantity: Decimal
    unit: str


@dataclass
class PicnicRecipeDetail:
    servings: int | None
    ingredients: list[PicnicRecipeIngredient] = field(default_factory=list)
    # Markdown using # headings per step -- the same subset ListrRecipe.instructions already
    # renders via MarkdownLite.tsx.
    instructions: str = ""


@dataclass
class PicnicDelivery:
    id: str
    # When it was actually dropped off -- the slot start if Picnic has no drop-off time, the
    # order time as a last resort. Timezone-aware, in Picnic's own (Dutch) offset.
    delivered_at: datetime
    # Sum of the delivery's completed orders' `total_price`: what the groceries cost, after
    # discounts and excluding deposit (statiegeld), which Picnic charges and refunds separately
    # through returned containers and would only add noise to "what did groceries cost".
    total_cents: int
    order_count: int


@dataclass
class PicnicOrder:
    id: str
    created_at: datetime
    # What Picnic charges for the order: groceries plus deposit -- usually what a bank statement
    # (and so a hand-booked gripr expense) shows.
    charged_cents: int
    # The groceries alone, after discounts, without deposit (what PicnicDelivery.total_cents sums).
    total_cents: int = 0


@dataclass
class PicnicDeliveryDetail:
    id: str
    orders: list[PicnicOrder] = field(default_factory=list)  # completed, uncancelled orders only
    # (Picnic product id, number of selling units) for everything those orders contained.
    articles: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class PicnicPromoProduct:
    product: PicnicProduct
    label: str  # Picnic's own offer text: "1+1 gratis", "25% korting", "2 voor €5"
    original_price: int | None = None  # cents, when Picnic shows a struck-through price


@dataclass
class PicnicPromoSection:
    title: str  # "Uitgelicht", "Fruit", "Kaas", ...
    products: list[PicnicPromoProduct] = field(default_factory=list)


class PicnicCheckoutError(Exception):
    """Picnic refused to start or pay for the checkout (e.g. the cart changed, a slot's cut-off
    passed, an age check) -- its own message is passed on to the reader."""


@dataclass
class PicnicCartLine:
    product_id: str
    name: str
    image_id: str | None
    unit_quantity: str
    count: int
    price_cents: int  # for the whole line, after any bundle discount


@dataclass
class PicnicCart:
    mts: int  # Picnic's modification timestamp; checkout must quote the current one
    lines: list[PicnicCartLine]
    total_cents: int  # groceries, after discounts
    deposit_cents: int
    checkout_total_cents: int  # what checkout charges
    selected_slot_id: str | None
    # "IMPLICIT": Picnic's own preselection; "EXPLICIT"/"ACTIVE": chosen.
    selected_slot_state: str | None


@dataclass
class PicnicSlot:
    id: str
    window_start: datetime
    window_end: datetime
    cut_off: datetime
    is_available: bool
    selected: bool
    minimum_order_cents: int | None
    unavailable_reason: str | None


@dataclass
class PicnicCheckout:
    order_id: str
    transaction_id: str
    # The bank's payment page (iDEAL) -- nothing is charged until the reader approves it there.
    payment_url: str


def picnic_image_url(image_id: str, size: str = "small") -> str:
    """Public, no auth needed (same path the picnic-api client uses)."""
    return f"{BASE_URL.split('/api/')[0]}/static/images/{image_id}/{size}.png"


class PicnicProvider:
    def __init__(self, base_url: str = BASE_URL, timeout: float = TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def _base_headers(self, auth_key: str | None) -> dict:
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Language": "nl",
        }
        if auth_key:
            headers["x-picnic-auth"] = auth_key
        return headers

    def _picnic_headers(self) -> dict:
        # Required alongside auth on the 2FA and catalog/cart endpoints, not on login itself.
        return {"x-picnic-agent": PICNIC_AGENT, "x-picnic-did": PICNIC_DEVICE_ID}

    def login(self, email: str, password: str) -> LoginResult:
        secret = hashlib.md5(password.encode("utf-8")).hexdigest()
        response = httpx.post(
            f"{self.base_url}/user/login",
            headers=self._base_headers(None),
            json={"key": email, "secret": secret, "client_id": CLIENT_ID},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic rejected that email/password.")
        response.raise_for_status()
        auth_key = response.headers.get("x-picnic-auth")
        if not auth_key:
            raise PicnicAuthError("Picnic login didn't return a session key.")
        return LoginResult(auth_key=auth_key, requires_2fa=bool(response.json().get("second_factor_authentication_required")))

    def generate_2fa_code(self, provisional_auth_key: str) -> None:
        """Triggers Picnic to text a code to the account's phone number."""
        response = httpx.post(
            f"{self.base_url}/user/2fa/generate",
            headers={**self._base_headers(provisional_auth_key), **self._picnic_headers()},
            json={"channel": "SMS"},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired before the code could be sent.")
        response.raise_for_status()

    def verify_2fa(self, provisional_auth_key: str, code: str) -> str:
        """Returns the real, usable auth key."""
        response = httpx.post(
            f"{self.base_url}/user/2fa/verify",
            headers={**self._base_headers(provisional_auth_key), **self._picnic_headers()},
            json={"otp": code},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("That code wasn't accepted.")
        response.raise_for_status()
        auth_key = response.headers.get("x-picnic-auth")
        if not auth_key:
            raise PicnicAuthError("Picnic didn't return a session key after verification.")
        return auth_key

    def search(self, auth_key: str, query: str) -> list[PicnicProduct]:
        response = httpx.get(
            f"{self.base_url}/pages/search-page-results",
            params={"search_term": query},
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        response.raise_for_status()
        return _extract_selling_units(response.json())

    def add_to_cart(self, auth_key: str, product_id: str, count: int = 1) -> None:
        response = httpx.post(
            f"{self.base_url}/cart/add_product",
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            json={"product_id": product_id, "count": count},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        response.raise_for_status()

    def _request(self, method: str, path: str, auth_key: str, json: object | None = None) -> object:
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            json=json,
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        response.raise_for_status()
        return response.json() if response.content else None

    def get_cart(self, auth_key: str) -> PicnicCart:
        return _parse_cart(self._request("GET", "/cart", auth_key))

    def remove_from_cart(self, auth_key: str, product_id: str, count: int = 1) -> PicnicCart:
        return _parse_cart(self._request("POST", "/cart/remove_product", auth_key, {"product_id": product_id, "count": count}))

    def get_delivery_slots(self, auth_key: str) -> list[PicnicSlot]:
        raw = self._request("GET", "/cart/delivery_slots", auth_key)
        return _parse_slots(raw.get("delivery_slots") if isinstance(raw, dict) else None)

    def set_delivery_slot(self, auth_key: str, slot_id: str) -> PicnicCart:
        return _parse_cart(self._request("POST", "/cart/set_delivery_slot", auth_key, {"slot_id": slot_id}))

    def checkout(self, auth_key: str, mts: int, return_url: str) -> PicnicCheckout:
        """Starts checkout for the cart as of `mts` (Picnic rejects a stale one) and starts the
        payment, returning the bank's payment page. The order is only placed once the reader
        approves the payment there; cancel_checkout abandons it."""
        started = self._checkout_call("POST", "/cart/checkout/start", auth_key, {"mts": mts, "oos_article_ids": None})
        order_id = str(started.get("order_id") or "")
        if not order_id:
            raise PicnicCheckoutError("Picnic startte geen bestelling.")
        payment = self._checkout_call(
            "POST", "/cart/checkout/initiate_payment", auth_key, {"order_id": order_id, "app_return_url": return_url}
        )
        action = payment.get("action") if isinstance(payment.get("action"), dict) else {}
        url = action.get("redirect_url") or payment.get("issuer_authentication_url")
        transaction_id = payment.get("transaction_id")
        if not url or not transaction_id:
            raise PicnicCheckoutError("Picnic gaf geen betaallink terug.")
        return PicnicCheckout(order_id=order_id, transaction_id=str(transaction_id), payment_url=str(url))

    def checkout_status(self, auth_key: str, transaction_id: str) -> str:
        """"FINISHED" once paid and placed; anything else means still in progress (or failed)."""
        raw = self._request("GET", f"/cart/checkout/{transaction_id}/status", auth_key)
        return str(raw.get("checkout_status")) if isinstance(raw, dict) else ""

    def cancel_checkout(self, auth_key: str, transaction_id: str) -> None:
        self._request("POST", "/cart/checkout/cancel", auth_key, {"transaction_id": transaction_id})

    def _checkout_call(self, method: str, path: str, auth_key: str, body: object) -> dict:
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            json=body,
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        if response.status_code >= 400:
            raise PicnicCheckoutError(_checkout_error_message(response))
        data = response.json() if response.content else {}
        return data if isinstance(data, dict) else {}

    def get_deliveries(self, auth_key: str) -> list[PicnicDelivery]:
        """Every completed delivery on the account, newest first -- Picnic returns the whole
        history (back to the account's first order) in one call, so callers filter by date."""
        response = httpx.post(
            f"{self.base_url}/deliveries/summary",
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            json=["COMPLETED"],
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        response.raise_for_status()
        return _parse_deliveries(response.json())

    def get_delivery_detail(self, auth_key: str, delivery_id: str) -> PicnicDeliveryDetail:
        """One delivery's orders with what each was charged, and every product it contained."""
        response = httpx.get(
            f"{self.base_url}/deliveries/{delivery_id}",
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        response.raise_for_status()
        return _parse_delivery_detail(delivery_id, response.json())

    def get_promotions(self, auth_key: str) -> list[PicnicPromoSection]:
        """The products on offer, as Picnic's own "Aanbiedingen" tab groups them."""
        return _parse_promo_page(self._request("GET", "/pages/promo-page-root", auth_key))

    def get_cookbook(self, auth_key: str) -> list[PicnicRecipeSummary]:
        """Every recipe tile on the cookbook page, across whichever sections Picnic shows
        (saved, self-created, weekly featured, ...) -- there's no keyword search for recipes,
        only this listing."""
        response = httpx.get(
            f"{self.base_url}/pages/cookbook-page-content",
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        response.raise_for_status()
        return _extract_recipe_tiles(response.json())

    def get_recipe_detail(self, auth_key: str, recipe_id: str) -> PicnicRecipeDetail:
        """Ingredients (real-world quantity + unit) and step-by-step instructions for one
        recipe, parsed from its details page -- see the module docstring's note on why this
        reads the instructions tab rather than the structured ingredients endpoint."""
        response = httpx.get(
            f"{self.base_url}/pages/selling-group-details-page",
            params={"selling_group_id": recipe_id},
            headers={**self._base_headers(auth_key), **self._picnic_headers()},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            raise PicnicAuthError("Picnic session expired.")
        response.raise_for_status()
        return _parse_instructions_tab(_collect_instructions_tab_text(response.json()))


def _parse_deliveries(raw: object) -> list[PicnicDelivery]:
    """The delivery summary list, reduced to what an order history needs. Only completed,
    uncancelled orders count toward a delivery's total; a delivery left with none (or with no
    usable date) is dropped rather than shown as a €0 delivery."""
    deliveries: list[PicnicDelivery] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict) or entry.get("status") != "COMPLETED":
            continue
        orders = [
            o for o in entry.get("orders") or []
            if isinstance(o, dict) and o.get("status") == "COMPLETED" and not o.get("cancellation_time")
            and isinstance(o.get("total_price"), int)
        ]
        delivered_at = _parse_time(
            (entry.get("delivery_time") or {}).get("start"),
            (entry.get("slot") or {}).get("window_start"),
            entry.get("creation_time"),
        )
        if not orders or delivered_at is None:
            continue
        deliveries.append(
            PicnicDelivery(
                id=str(entry.get("delivery_id") or entry.get("id")),
                delivered_at=delivered_at,
                total_cents=sum(o["total_price"] for o in orders),
                order_count=len(orders),
            )
        )
    return sorted(deliveries, key=lambda d: d.delivered_at, reverse=True)


def _parse_delivery_detail(delivery_id: str, raw: object) -> PicnicDeliveryDetail:
    """Orders as ORDER objects; within each, ORDER_LINE items wrap one or more ORDER_ARTICLE
    items whose QUANTITY decorator says how many selling units were delivered (1 if absent)."""
    detail = PicnicDeliveryDetail(id=delivery_id)
    for order in (raw.get("orders") if isinstance(raw, dict) else None) or []:
        if not isinstance(order, dict) or order.get("status") != "COMPLETED" or order.get("cancellation_time"):
            continue
        created_at = _parse_time(order.get("creation_time"))
        total = order.get("total_price")
        charged = order.get("checkout_total_price")
        if not isinstance(charged, int):
            charged = total
        if created_at is None or not isinstance(charged, int):
            continue
        detail.orders.append(
            PicnicOrder(
                id=str(order.get("id")), created_at=created_at, charged_cents=charged,
                total_cents=total if isinstance(total, int) else charged,
            )
        )
        for line in order.get("items") or []:
            for article in (line.get("items") if isinstance(line, dict) else None) or []:
                if not isinstance(article, dict) or article.get("type") != "ORDER_ARTICLE" or not article.get("id"):
                    continue
                quantity = next(
                    (d.get("quantity") for d in article.get("decorators") or []
                     if isinstance(d, dict) and d.get("type") == "QUANTITY" and isinstance(d.get("quantity"), int)),
                    1,
                )
                detail.articles.append((str(article["id"]), quantity))
    return detail


def _checkout_error_message(response: httpx.Response) -> str:
    """Picnic's own explanation where it gives one (it's shown to the reader as-is)."""
    try:
        data = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        error = data.get("error") if isinstance(data.get("error"), dict) else data
        for key in ("message", "title", "description", "code"):
            if isinstance(error.get(key), str) and error[key]:
                return error[key]
    return f"Picnic weigerde de bestelling (HTTP {response.status_code})."


def _parse_cart(raw: object) -> PicnicCart:
    raw = raw if isinstance(raw, dict) else {}
    lines: list[PicnicCartLine] = []
    for line in raw.get("items") or []:
        if not isinstance(line, dict):
            continue
        articles = [a for a in line.get("items") or [] if isinstance(a, dict) and a.get("type") == "ORDER_ARTICLE"]
        if not articles:
            continue
        article = articles[0]
        count = next(
            (d.get("quantity") for d in article.get("decorators") or []
             if isinstance(d, dict) and d.get("type") == "QUANTITY" and isinstance(d.get("quantity"), int)),
            1,
        )
        # A bundle discount shows as a PRICE decorator on the line; otherwise the line's own price.
        price = next(
            (d.get("display_price") for d in line.get("decorators") or []
             if isinstance(d, dict) and d.get("type") == "PRICE" and isinstance(d.get("display_price"), int)),
            line.get("display_price") if isinstance(line.get("display_price"), int) else line.get("price"),
        )
        image_ids = article.get("image_ids") or []
        lines.append(
            PicnicCartLine(
                product_id=str(article.get("id")),
                name=article.get("name") or "",
                image_id=image_ids[0] if image_ids else None,
                unit_quantity=article.get("unit_quantity") or "",
                count=count,
                price_cents=price if isinstance(price, int) else 0,
            )
        )
    selected = raw.get("selected_slot") if isinstance(raw.get("selected_slot"), dict) else {}
    return PicnicCart(
        mts=int(raw.get("mts") or 0),
        lines=lines,
        total_cents=int(raw.get("total_price") or 0),
        deposit_cents=int(raw.get("total_deposit") or 0),
        checkout_total_cents=int(raw.get("checkout_total_price") or raw.get("total_price") or 0),
        selected_slot_id=selected.get("slot_id"),
        selected_slot_state=selected.get("state"),
    )


def _parse_slots(raw: object) -> list[PicnicSlot]:
    slots: list[PicnicSlot] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict) or not entry.get("slot_id"):
            continue
        start, end, cut_off = (_parse_time(entry.get(k)) for k in ("window_start", "window_end", "cut_off_time"))
        if start is None or end is None or cut_off is None:
            continue
        minimum = entry.get("minimum_order_value")
        slots.append(
            PicnicSlot(
                id=str(entry["slot_id"]),
                window_start=start,
                window_end=end,
                cut_off=cut_off,
                is_available=bool(entry.get("is_available")),
                selected=bool(entry.get("selected")),
                minimum_order_cents=minimum if isinstance(minimum, int) else None,
                unavailable_reason=entry.get("unavailability_reason"),
            )
        )
    return sorted(slots, key=lambda x: (x.window_start, x.window_end))


_COLOR_MARKUP_RE = re.compile(r"#\(#[0-9a-fA-F]{6}\)")


def _first_markdown(node: object) -> str | None:
    """The first text in a PML subtree, without Picnic's `#(#rrggbb)` colour markup."""
    if isinstance(node, dict):
        text = node.get("markdown")
        if isinstance(text, str):
            cleaned = _COLOR_MARKUP_RE.sub("", text).strip()
            if cleaned:
                return cleaned
        for value in node.values():
            found = _first_markdown(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _first_markdown(value)
            if found:
                return found
    return None


def _promo_tiles(node: object, out: list[PicnicPromoProduct], seen: set[str]) -> None:
    """Product tiles in a promo section: a node whose analytics contexts carry the offer
    (`promotion_label`, and `strikethrough_price` when shown) and which contains the product's
    `sellingUnit`. Each product once per section, in page order."""
    if isinstance(node, dict):
        contexts = (node.get("analytics") or {}).get("contexts") if isinstance(node.get("analytics"), dict) else None
        promo = next(
            (c["data"] for c in contexts or []
             if isinstance(c, dict) and isinstance(c.get("data"), dict) and c["data"].get("promotion_label")),
            None,
        )
        if promo is not None:
            units = _extract_selling_units(node)
            if units and units[0].id not in seen:
                seen.add(units[0].id)
                strike = promo.get("strikethrough_price")
                out.append(
                    PicnicPromoProduct(
                        product=units[0],
                        label=_COLOR_MARKUP_RE.sub("", str(promo["promotion_label"])).strip(),
                        original_price=int(strike) if promo.get("show_strikethrough_price") and isinstance(strike, (int, float)) else None,
                    )
                )
            return
        for value in node.values():
            _promo_tiles(value, out, seen)
    elif isinstance(node, list):
        for value in node:
            _promo_tiles(value, out, seen)


def _parse_promo_page(raw: object) -> list[PicnicPromoSection]:
    """Picnic's promo page is a Fusion page whose content block holds one BLOCK (or SUSPENSE,
    for the personal "Keuzekorting" box) per section, titled by its first text. Anything that
    doesn't look like that is skipped rather than failing -- this is UI markup, not an API."""
    try:
        body = raw["layout"]["body"]["child"]["child"]["children"]
    except (KeyError, TypeError):
        return []
    sections: list[PicnicPromoSection] = []
    for block in body if isinstance(body, list) else []:
        for child in (block.get("children") if isinstance(block, dict) else None) or []:
            if not isinstance(child, dict) or child.get("type") not in ("BLOCK", "SUSPENSE"):
                continue
            products: list[PicnicPromoProduct] = []
            _promo_tiles(child, products, set())
            if products:
                sections.append(PicnicPromoSection(title=_first_markdown(child) or "Aanbiedingen", products=products))
    return sections


def _parse_time(*candidates: object) -> datetime | None:
    """The first candidate that's a valid ISO timestamp ("2026-09-20T15:27:11.223+02:00")."""
    for value in candidates:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                continue
    return None


def _extract_selling_units(node: object) -> list[PicnicProduct]:
    """Picnic's search endpoint returns a full native-app page description (a "Fusion" page, in
    Picnic's own UI-markup format) rather than a clean product list -- every SELLING_UNIT_TILE
    component anywhere in that tree carries one product. Walked recursively rather than via a
    JSONPath dependency (what the npm wrapper uses), since this is the one place that needs it.
    Deduplicated by id: the same product can legitimately appear in more than one tile (e.g. a
    promotional banner) on the same results page.
    """
    found: dict[str, PicnicProduct] = {}

    def walk(value: object) -> None:
        if isinstance(value, dict):
            selling_unit = value.get("sellingUnit")
            if isinstance(selling_unit, dict) and selling_unit.get("id"):
                product = PicnicProduct(
                    id=selling_unit["id"],
                    name=selling_unit.get("name") or "",
                    unit_quantity=selling_unit.get("unit_quantity") or "",
                    display_price=selling_unit.get("display_price"),
                    image_id=selling_unit.get("image_id"),
                )
                # A product repeated in a sparser tile (a banner) keeps what the fuller one had.
                earlier = found.get(product.id)
                if earlier is not None:
                    product.name = product.name or earlier.name
                    product.unit_quantity = product.unit_quantity or earlier.unit_quantity
                    product.display_price = product.display_price if product.display_price is not None else earlier.display_price
                    product.image_id = product.image_id or earlier.image_id
                found[product.id] = product
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(node)
    return list(found.values())


_RECIPE_ID_RE = re.compile(r"selling_group_id=([a-f0-9]+)")
_RECIPE_NAME_RE = re.compile(r"[?&]name=([^&]+)")


def _extract_recipe_tiles(node: object) -> list[PicnicRecipeSummary]:
    """Recipe tiles on the cookbook page are `TOUCHABLE` PML components whose `onPress.target`
    is an in-app link embedding the recipe id (`...selling-group-details-page,selling_group_id=
    <id>`) and whose `onLongPress.target` (the "hold for options" action) embeds the display
    name as a URL query param -- both plain string patterns, no Fusion-specific library needed.
    Deduplicated by id (the same recipe can appear in more than one section, e.g. both "this
    week" and "saved"); the first section seen for it wins.
    """
    found: dict[str, PicnicRecipeSummary] = {}

    def walk(value: object, segment: str | None) -> None:
        if isinstance(value, dict):
            contexts = (value.get("analytics") or {}).get("contexts")
            if isinstance(contexts, list):
                for ctx in contexts:
                    data = ctx.get("data") if isinstance(ctx, dict) else None
                    if isinstance(data, dict) and isinstance(data.get("segment_type"), str):
                        segment = data["segment_type"]

            if value.get("type") == "TOUCHABLE":
                target = (value.get("onPress") or {}).get("target")
                match = _RECIPE_ID_RE.search(target) if isinstance(target, str) else None
                if match and match.group(1) not in found:
                    long_press_target = (value.get("onLongPress") or {}).get("target")
                    name_match = _RECIPE_NAME_RE.search(long_press_target) if isinstance(long_press_target, str) else None
                    found[match.group(1)] = PicnicRecipeSummary(
                        id=match.group(1),
                        name=unquote(name_match.group(1)) if name_match else "",
                        segment=segment,
                    )

            for v in value.values():
                walk(v, segment)
        elif isinstance(value, list):
            for v in value:
                walk(v, segment)

    walk(node, None)
    return list(found.values())


def _find_by_id(node: object, target_id: str) -> object | None:
    if isinstance(node, dict):
        if node.get("id") == target_id:  # `==`, not `in` a set -- some ids are dicts (EXPRESSIONs)
            return node
        for v in node.values():
            found = _find_by_id(v, target_id)
            if found is not None:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_by_id(v, target_id)
            if found is not None:
                return found
    return None


def _collect_instructions_tab_text(node: object) -> list[str]:
    """Every markdown string inside the `selling-group-tab-instructions` component, in document
    order. That component (a stable id on Picnic's recipe details page, confirmed against a
    live recipe) contains the ingredient list *and* the step-by-step instructions as plain
    RICH_TEXT, despite its name suggesting only the latter."""
    tab = _find_by_id(node, "selling-group-tab-instructions")
    if tab is None:
        return []

    texts: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            markdown = value.get("markdown")
            if isinstance(markdown, str):
                texts.append(markdown)
            for v in value.values():
                collect(v)
        elif isinstance(value, list):
            for v in value:
                collect(v)

    collect(tab)
    return texts


_INGREDIENT_LINE_RE = re.compile(r"^\*\*(.+?)\*\*\s+([\d.,]+)\s*(.+)$")
_PANTRY_STAPLES_RE = re.compile(r"^\*\*(uit eigen keuken:?)\*\*\s*(.+)$", re.IGNORECASE)
_PORTIONS_RE = re.compile(r"^(\d+)\s*porties?$")
_STEP_HEADER_RE = re.compile(r"^Stap\s+\d+$")


def _parse_instructions_tab(texts: list[str]) -> PicnicRecipeDetail:
    """State machine over the instructions tab's markdown strings, in the exact order Picnic
    renders them: an "Ingrediënten" header, lines shaped `**name** quantity unit`, a
    "Bereidingswijze" header, a "N porties" line, then alternating "Stap N" / body pairs, and
    an optional trailing "Tip" / body pair. A "Notitie" marks the start of the *user's own*
    editable note placeholder, never real recipe content, so parsing stops there.

    This is undocumented page structure, not a stable API contract -- it may need updates if
    Picnic changes these templates, the same caveat the community wrapper carries for its own
    equivalent (Fusion/PML) parsing.
    """
    ingredients: list[PicnicRecipeIngredient] = []
    servings: int | None = None
    step_blocks: list[str] = []
    section = "ingredients"
    pending_header: str | None = None

    for raw in texts:
        text = raw.strip()
        if not text or text == "Ingrediënten":
            continue
        if text == "Bereidingswijze":
            section = "instructions"
            continue
        if text == "Notitie":
            break

        if section == "ingredients":
            pantry_match = _PANTRY_STAPLES_RE.match(text)
            ingredient_match = _INGREDIENT_LINE_RE.match(text)
            if pantry_match:
                # Picnic's pantry-staples catch-all, e.g. "**Uit eigen keuken:** 1.5 teentjes
                # knoflook en 0.75 el zonnebloemolie" -- combines more than one item in a single
                # line, checked *before* the generic pattern below (which would otherwise match
                # the leading quantity and mangle the rest into a garbled "unit"). Kept as one
                # freeform ingredient rather than guessing how to split it.
                ingredients.append(PicnicRecipeIngredient(name=pantry_match.group(2).strip(), quantity=Decimal(1), unit=""))
            elif ingredient_match:
                name, quantity, unit = ingredient_match.groups()
                ingredients.append(
                    PicnicRecipeIngredient(name=name.strip(), quantity=Decimal(quantity.replace(",", ".")), unit=unit.strip())
                )
            else:
                # Doesn't fit any recognized pattern -- kept as one freeform ingredient rather
                # than dropping real content.
                ingredients.append(PicnicRecipeIngredient(name=text, quantity=Decimal(1), unit=""))
            continue

        # section == "instructions"
        if pending_header is not None:
            step_blocks.append(f"# {pending_header}\n\n{text}")
            pending_header = None
            continue
        portions_match = _PORTIONS_RE.match(text)
        if portions_match:
            servings = int(portions_match.group(1))
            continue
        if text.startswith("**Let op:**"):
            continue
        if _STEP_HEADER_RE.match(text) or text == "Tip":
            pending_header = text
            continue
        step_blocks.append(text)  # unrecognized prose -- keep it rather than silently drop it

    return PicnicRecipeDetail(servings=servings, ingredients=ingredients, instructions="\n\n".join(step_blocks))


picnic_provider = PicnicProvider()
