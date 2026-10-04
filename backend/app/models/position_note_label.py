from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# A note can carry several labels at once, same reasoning listr's recipe categories already
# use for the same "several tags on one row" shape (see docs/adr/0006-listr-meal-planning.md).
position_note_label_links = Table(
    "position_note_label_links",
    Base.metadata,
    Column("note_id", ForeignKey("position_notes.id"), primary_key=True),
    Column("label_id", ForeignKey("position_note_labels.id"), primary_key=True),
)


class PositionNoteLabel(Base):
    """A reusable tag for journal entries (e.g. "Thesis", "Risk", "Earnings") -- global across
    every position, not per-asset, so the same label filters consistently in the Journal view
    regardless of which holding a note is about."""

    __tablename__ = "position_note_labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    notes = relationship("PositionNote", secondary=position_note_label_links, back_populates="labels")
