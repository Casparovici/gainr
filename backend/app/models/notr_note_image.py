from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db import Base


class NotrNoteImage(Base):
    """A picture in a note's Markdown. The bytes live in the row (like gardnr's log photos and
    listr's recipe photos), so the whole-database backup covers them; `content` is deferred so
    listing notes never reads a picture. A picture is uploaded before its note is saved, so
    `note_id` is empty until the note's body references it (notr_note_service.sync_images)."""

    __tablename__ = "notr_note_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("notr_notes.id"), nullable=True, index=True)
    # Decided by sniffing the bytes and re-encoding, never taken from the upload.
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    content: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
