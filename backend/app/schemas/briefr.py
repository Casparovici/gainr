from datetime import date as date_, datetime
from decimal import Decimal
from urllib.parse import urlsplit

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.models.briefr_report import BriefrAttention, BriefrVerdict

# -- the report file an agent commits (docs/adr/0044) ---------------------------------------------
# Untrusted input: written by an agent that read the open web. Every field is bounded, links are
# http(s) only, and unknown keys are ignored rather than refused, so an agent that adds a field
# doesn't lose its whole night's report.

AGENT_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
MAX_ITEMS = 200
MAX_SOURCES = 10
MAX_INGREDIENTS = 60
MAX_STEPS = 40


def _is_http_link(value: str, max_length: int = 2000) -> bool:
    parts = urlsplit(value)
    return len(value) <= max_length and parts.scheme in ("http", "https") and bool(parts.netloc)


class ReportFileIngredient(BaseModel):
    """One ingredient line of a suggested recipe. `name` is the product, in the catalog's own
    words where one fits (context/listr-products.md); quantity and unit are optional, so "zout en
    peper" is a line too."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    quantity: Decimal | None = Field(default=None, ge=0, le=100_000, max_digits=12, decimal_places=3)
    unit: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("unit", "note")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return " ".join((value or "").split()) or None


class ReportFileRecipe(BaseModel):
    """A recipe a finding suggests (the home chef's), complete enough to become a listr recipe
    without the server fetching the page: the agent read it, the server never does (ADR 0054)."""

    model_config = ConfigDict(extra="ignore")

    url: str = Field(max_length=500)
    servings: int | None = Field(default=None, ge=1, le=50)
    minutes: int | None = Field(default=None, ge=1, le=1440)
    ingredients: list[ReportFileIngredient] = Field(min_length=1, max_length=MAX_INGREDIENTS)
    steps: list[str] = Field(min_length=1, max_length=MAX_STEPS)

    @field_validator("url")
    @classmethod
    def _http_link(cls, value: str) -> str:
        if not _is_http_link(value, 500):
            raise ValueError(f"not an http(s) link: {value[:80]!r}")
        return value

    @field_validator("steps")
    @classmethod
    def _steps(cls, values: list[str]) -> list[str]:
        steps = [" ".join(step.split()) for step in values]
        if any(not step for step in steps):
            raise ValueError("a step must not be blank")
        if any(len(step) > 2000 for step in steps):
            raise ValueError("a step is longer than 2000 characters")
        return steps


class ReportFileItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # "ticker" is accepted too: it's the word an agent reaches for.
    symbol: str | None = Field(default=None, max_length=32, validation_alias=AliasChoices("symbol", "ticker"))
    verdict: BriefrVerdict
    headline: str = Field(min_length=1, max_length=300)
    detail: str | None = Field(default=None, max_length=5000)
    sources: list[str] = Field(default_factory=list, max_length=MAX_SOURCES)
    recipe: ReportFileRecipe | None = None

    @field_validator("symbol", "detail")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("headline")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("sources")
    @classmethod
    def _http_links_only(cls, values: list[str]) -> list[str]:
        for value in values:
            if not _is_http_link(value):
                raise ValueError(f"not an http(s) link: {value[:80]!r}")
        return values


class ReportFileFront(BaseModel):
    """The `+++`-fenced TOML header of a report file."""

    model_config = ConfigDict(extra="ignore")

    agent: str = Field(pattern=AGENT_PATTERN)
    run_at: datetime
    title: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=1000)
    attention: BriefrAttention | None = None
    items: list[ReportFileItem] = Field(default_factory=list, max_length=MAX_ITEMS)

    @field_validator("run_at")
    @classmethod
    def _has_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("needs a UTC offset, e.g. 2026-10-19T02:14:00+02:00")
        return value

    @field_validator("title")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("summary")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


# -- the API ---------------------------------------------------------------------------------------


class VerdictCountsOut(BaseModel):
    act: int
    watch: int
    ignore: int


class BriefrIngredientOut(BaseModel):
    name: str
    quantity: Decimal | None
    unit: str | None
    note: str | None


class BriefrRecipeOut(BaseModel):
    """A suggested recipe, and where it stands in listr: the recipe it became (matched by its
    URL) and the days it's planned on since the report ran."""

    url: str
    servings: int | None
    minutes: int | None
    ingredients: list[BriefrIngredientOut]
    steps: list[str]
    listr_recipe_id: int | None = None
    planned_on: list[date_] = []


class BriefrItemOut(BaseModel):
    id: int
    symbol: str | None
    # The gainr asset `symbol` resolved to, if any, so the item can link to its position.
    asset_id: int | None
    verdict: BriefrVerdict
    headline: str
    detail: str | None
    sources: list[str]
    recipe: BriefrRecipeOut | None = None


class BriefrReportOut(BaseModel):
    """A report in the inbox list: everything but its body and findings."""

    id: int
    agent: str
    run_at: datetime
    title: str
    summary: str | None
    attention: BriefrAttention
    is_read: bool
    is_archived: bool
    counts: VerdictCountsOut


class BriefrReportDetailOut(BriefrReportOut):
    source_path: str
    body: str
    items: list[BriefrItemOut]


class BriefrAgentOut(BaseModel):
    agent: str
    last_run_at: datetime
    report_count: int
    unread_count: int


class BriefrReadIn(BaseModel):
    is_read: bool


class BriefrArchivedIn(BaseModel):
    is_archived: bool


class BriefrPlanIn(BaseModel):
    """Plan a suggested recipe in listr's weekplanner. A day that already has something planned
    is only replaced with `replace`."""

    date: date_
    replace: bool = False
