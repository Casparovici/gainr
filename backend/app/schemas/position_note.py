from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class PositionNoteLabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    color: str | None = None
    is_archived: bool


class PositionNoteLabelCreate(BaseModel):
    name: str


class PositionNoteLabelUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_archived: bool | None = None


class PositionNoteLabelReorder(BaseModel):
    label_ids: list[int]


class PositionNoteCreate(BaseModel):
    title: str
    body: str
    label_ids: list[int] = []


class PositionNoteUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    # None means "leave labels alone"; [] means "clear every label" -- distinguished via
    # exclude_unset in the router, same convention every other partial-update payload here uses.
    label_ids: list[int] | None = None


class JournalNoteCreate(PositionNoteCreate):
    """Created from the Journal, where the note can be about several positions at once."""

    asset_ids: list[int] = Field(min_length=1)


class JournalNoteUpdate(PositionNoteUpdate):
    # None means "leave the linked positions alone"; a note always keeps at least one.
    asset_ids: list[int] | None = Field(default=None, min_length=1)


class NoteAssetOut(BaseModel):
    """One position a note is about -- enough to name it and link to it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str


class PositionNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Every position the note is linked to, ordered by ticker (see PositionNote.assets).
    assets: list[NoteAssetOut] = []
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
    labels: list[PositionNoteLabelOut] = []

    # SQLite's CURRENT_TIMESTAMP (what server_default=func.now() resolves to) is UTC but comes
    # back as a naive datetime — nothing in the value itself says so. Serialized as-is, the
    # frontend's `new Date(iso)` reads a timezone-less string as *local* time, which quietly
    # shifted every "created just now" note to "2 hours ago" for anyone not on UTC. Stamping
    # the offset explicitly here is the fix; it has no effect on already-aware values.
    @field_serializer("created_at", "updated_at")
    def _as_utc(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
