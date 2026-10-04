from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.position_note_label import position_note_label_links

# A journal entry can be about several holdings at once (a sector thesis, a comparison), so the
# note<->position link is its own association table -- the same many-to-many shape labels use.
# See docs/adr/0024-journal-notes-on-multiple-positions.md.
position_note_assets = Table(
    "position_note_assets",
    Base.metadata,
    Column("note_id", ForeignKey("position_notes.id"), primary_key=True),
    Column("asset_id", ForeignKey("assets.id"), primary_key=True, index=True),
)


class PositionNote(Base):
    """A journal entry about one or more holdings — a title plus free-text body (rendered with a small
    markdown subset on the frontend: bold, italic, code). Distinct from `Asset.notes`, a single
    unused free-text field left over from an earlier design; this is the one the UI writes to.

    The same rows back both the per-position Notes tab (`GET /assets/{id}/notes`) and the
    cross-position Journal tab (`GET /journal/notes`) -- one table, two views, so an entry added
    from either place is immediately visible from the other with no sync step. A note linked to
    several positions shows up on each of their Notes tabs."""

    __tablename__ = "position_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    assets = relationship(
        "Asset", secondary=position_note_assets, back_populates="position_notes", order_by="Asset.ticker",
    )
    labels = relationship(
        "PositionNoteLabel", secondary=position_note_label_links, back_populates="notes",
        order_by="PositionNoteLabel.sort_order",
    )
