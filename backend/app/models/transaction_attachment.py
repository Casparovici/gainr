from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db import Base


class TransactionAttachment(Base):
    """A file (an invoice, a contract note) attached to a gainr transaction.

    The bytes live in the database, not on disk, like gardnr's log photos: portfolio.db is the one
    thing backed up and restored (docs/adr/0013), so a file stored next to it would silently fall
    out of the backup. `content` is deferred so listing a transaction's attachments never reads
    the files themselves.
    """

    __tablename__ = "transaction_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    # Decided by sniffing the bytes (transaction_attachment_service), never taken from the upload.
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
