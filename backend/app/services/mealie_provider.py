"""Client for the user's self-hosted Mealie recipe app (https://mealie.io), read-only: it lists
recipes and fetches one recipe's details, nothing else. See docs/adr/0022-listr-mealie-import.md.

Mealie's JSON is treated as untrusted input: every field is type-checked, trimmed and
length-capped here, so what reaches listr_mealie_service is always plain, bounded data --
nothing downstream has to wonder whether a "name" is really a string.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

TIMEOUT = 15.0
PAGE_SIZE = 100
# Hard stop for pagination, far above any personal recipe collection -- only there so a
# misbehaving server that keeps reporting more pages can't loop us forever.
MAX_PAGES = 50
MAX_IMAGE_BYTES = 25 * 1024 * 1024


class MealieError(Exception):
    """Mealie couldn't be reached, or answered with something that isn't a usable response."""


class MealieAuthError(MealieError):
    """Mealie rejected the API key (401/403) -- the reader needs a new token, retrying won't help."""


@dataclass
class MealieRecipeSummary:
    id: str
    slug: str
    name: str
    updated_at: str


@dataclass
class MealieIngredient:
    quantity: Decimal | None
    unit: str | None
    food_id: str | None
    food_name: str | None
    note: str
    # Mealie's own one-line rendering ("8 stuks bladerdeeg uit de vriezer") -- the fallback text
    # for an ingredient that has no food attached (an unparsed line).
    display: str


@dataclass
class MealieRecipe:
    id: str
    slug: str
    name: str
    updated_at: str
    servings: int | None
    description: str
    notes: list[str] = field(default_factory=list)
    ingredients: list[MealieIngredient] = field(default_factory=list)
    # (title, text) per step; title is "" for an untitled step.
    instructions: list[tuple[str, str]] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    # Mealie's `image` field is set when the recipe has a picture; the bytes come from get_image.
    has_image: bool = False


def _text(value: object, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _quantity(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        quantity = Decimal(str(value))
    except InvalidOperation:
        return None
    if not quantity.is_finite() or quantity <= 0:
        return None
    return quantity.quantize(Decimal("0.001"))


def _servings(value: object) -> int | None:
    quantity = _quantity(value)
    if quantity is None:
        return None
    servings = int(quantity)
    return servings if 0 < servings <= 1000 else None


def _parse_ingredient(raw: object) -> MealieIngredient | None:
    if not isinstance(raw, dict):
        return None
    unit = raw.get("unit") if isinstance(raw.get("unit"), dict) else {}
    food = raw.get("food") if isinstance(raw.get("food"), dict) else {}
    unit_label = _text(unit.get("abbreviation"), 32) or _text(unit.get("name"), 32) or None
    food_id = _text(food.get("id"), 64) or None
    food_name = _text(food.get("name"), 120) or None
    display = _text(raw.get("display"), 300) or _text(raw.get("originalText"), 300)
    note = _text(raw.get("note"), 300)
    if food_id is None and not (display or note):
        return None
    return MealieIngredient(
        quantity=_quantity(raw.get("quantity")),
        unit=unit_label,
        food_id=food_id,
        food_name=food_name if food_id else None,
        note=note,
        display=display or note,
    )


class MealieProvider:
    def __init__(self, base_url: str, api_key: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/api",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=TIMEOUT,
            transport=transport,
            # Only ever the configured host: never follow a redirect somewhere else with the key.
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise MealieError(f"Mealie is niet bereikbaar ({type(exc).__name__})") from exc
        if response.status_code in (401, 403):
            raise MealieAuthError("Mealie weigerde de API-sleutel")
        if response.status_code != 200:
            raise MealieError(f"Mealie antwoordde met HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise MealieError("Mealie stuurde geen geldige JSON") from exc
        if not isinstance(data, dict):
            raise MealieError("Onverwacht antwoord van Mealie")
        return data

    def list_recipes(self) -> list[MealieRecipeSummary]:
        summaries: list[MealieRecipeSummary] = []
        for page in range(1, MAX_PAGES + 1):
            data = self._get("/recipes", params={"page": page, "perPage": PAGE_SIZE})
            items = data.get("items") if isinstance(data.get("items"), list) else []
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                recipe_id, slug = _text(raw.get("id"), 64), _text(raw.get("slug"), 200)
                if recipe_id and slug:
                    summaries.append(
                        MealieRecipeSummary(
                            id=recipe_id,
                            slug=slug,
                            name=_text(raw.get("name"), 200) or slug,
                            updated_at=_text(raw.get("updatedAt") or raw.get("dateUpdated"), 64),
                        )
                    )
            total_pages = data.get("total_pages", data.get("totalPages"))
            if not items or not isinstance(total_pages, int) or page >= total_pages:
                break
        return summaries

    def get_recipe(self, slug: str) -> MealieRecipe:
        # The slug came from Mealie's own list response; quote it anyway so a stray "/" or "?"
        # in one can't turn into a different path on the same host.
        data = self._get(f"/recipes/{quote(slug, safe='')}")
        recipe_id = _text(data.get("id"), 64)
        if not recipe_id:
            raise MealieError("Recept zonder id ontvangen van Mealie")

        ingredients = [i for i in (_parse_ingredient(raw) for raw in data.get("recipeIngredient") or []) if i]
        instructions = []
        for raw in data.get("recipeInstructions") or []:
            if isinstance(raw, dict) and (text := _text(raw.get("text"), 5000)):
                instructions.append((_text(raw.get("title"), 200), text))
        notes = []
        for raw in data.get("notes") or []:
            if isinstance(raw, dict):
                title, text = _text(raw.get("title"), 200), _text(raw.get("text"), 5000)
                if text:
                    notes.append(f"**{title}**\n{text}" if title else text)
        categories = []
        for key in ("recipeCategory", "tags"):
            for raw in data.get(key) or []:
                if isinstance(raw, dict) and (name := _text(raw.get("name"), 120)) and name not in categories:
                    categories.append(name)

        return MealieRecipe(
            id=recipe_id,
            slug=_text(data.get("slug"), 200) or slug,
            name=_text(data.get("name"), 200) or slug,
            updated_at=_text(data.get("updatedAt") or data.get("dateUpdated"), 64),
            servings=_servings(data.get("recipeServings")),
            description=_text(data.get("description"), 5000),
            notes=notes,
            ingredients=ingredients,
            instructions=instructions,
            categories=categories,
            has_image=bool(_text(data.get("image"), 64)),
        )

    def get_image(self, recipe_id: str) -> bytes | None:
        """The recipe's picture as Mealie stores it, or None when it has none (or isn't a usable
        image response). Only the bytes are returned; listr_recipe_service validates and re-encodes
        them like any upload. Capped so a misbehaving server can't make us buffer something huge."""
        try:
            response = self._client.get(f"/media/recipes/{quote(recipe_id, safe='')}/images/original.webp")
        except httpx.HTTPError as exc:
            raise MealieError(f"Mealie is niet bereikbaar ({type(exc).__name__})") from exc
        if response.status_code in (401, 403):
            raise MealieAuthError("Mealie weigerde de API-sleutel")
        if response.status_code == 404:
            return None
        if response.status_code != 200 or not response.content or len(response.content) > MAX_IMAGE_BYTES:
            return None
        return response.content
