from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# A note can carry several labels at once, same reasoning listr's recipe categories use for the
# same "several tags on one row" shape (see docs/adr/0006-listr-meal-planning.md).
notr_note_label_links = Table(
    "notr_note_label_links",
    Base.metadata,
    Column("note_id", ForeignKey("notr_notes.id"), primary_key=True),
    Column("label_id", ForeignKey("notr_labels.id"), primary_key=True),
)


class NotrLabel(Base):
    """A reusable tag for notes (e.g. "Thesis", "Risk", "Idea") -- global across every note, so
    the same label filters consistently in notr and in gainr's Journal. These are the labels the
    Journal always had (docs/adr/0016), moved here by docs/adr/0050."""

    __tablename__ = "notr_labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    notes = relationship("NotrNote", secondary=notr_note_label_links, back_populates="labels")
