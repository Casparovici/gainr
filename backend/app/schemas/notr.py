from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer

MAX_TITLE = 200
# Far more than a note needs; it only stops a runaway paste from landing in the database.
MAX_BODY = 200_000


class NotrLabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    color: str | None = None
    is_archived: bool


class NotrLabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class NotrLabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: str | None = None
    is_archived: bool | None = None


class NotrLabelReorder(BaseModel):
    label_ids: list[int]


class NotrNoteCreate(BaseModel):
    title: str = Field(default="", max_length=MAX_TITLE)
    body: str = Field(default="", max_length=MAX_BODY)
    pinned: bool = False
    label_ids: list[int] = []
    asset_ids: list[int] = []
    plant_ids: list[int] = []
    recipe_ids: list[int] = []
    # The day the note is about, for one written earlier somewhere else (an import from another
    # notebook). Omitted, the note is dated now, as ever.
    created_at: datetime | None = None


class NotrNoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    body: str | None = Field(default=None, max_length=MAX_BODY)
    pinned: bool | None = None
    is_archived: bool | None = None
    # None means "leave them alone"; [] means "clear every one" -- distinguished via exclude_unset
    # in the router, same convention every other partial-update payload here uses.
    label_ids: list[int] | None = None
    asset_ids: list[int] | None = None
    plant_ids: list[int] | None = None
    recipe_ids: list[int] | None = None


class NotrAssetOut(BaseModel):
    """A position a note is about -- enough to name it and link to it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str


class NotrPlantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class NotrRecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class NotrNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    pinned: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    # What the note is about, each ordered by name (see NotrNote).
    assets: list[NotrAssetOut] = []
    plants: list[NotrPlantOut] = []
    recipes: list[NotrRecipeOut] = []
    labels: list[NotrLabelOut] = []

    # SQLite's CURRENT_TIMESTAMP (what server_default=func.now() resolves to) is UTC but comes
    # back as a naive datetime -- nothing in the value itself says so. Serialized as-is, the
    # frontend's `new Date(iso)` reads a timezone-less string as *local* time, which quietly
    # shifted every "created just now" note to "2 hours ago" for anyone not on UTC. Stamping
    # the offset explicitly here is the fix; it has no effect on already-aware values.
    @field_serializer("created_at", "updated_at")
    def _as_utc(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class NotrImageOut(BaseModel):
    """A stored picture; `url` is what goes in the note's Markdown."""

    id: int
    url: str
    content_type: str
    size_bytes: int


class NotrPinnedNoteOut(BaseModel):
    """A pinned note, as Vandaag lists it."""

    id: int
    title: str
    # The first line of the body, for a note without a title.
    preview: str
