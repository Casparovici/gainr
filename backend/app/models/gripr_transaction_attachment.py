from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db import Base


class GriprTransactionAttachment(Base):
    """A file (an invoice, a receipt) attached to a gripr transaction -- the same thing, for the
    same reasons, as gainr's TransactionAttachment (docs/adr/0035): the bytes live in the row so
    the backup covers them, `content` is deferred so listing never reads a file."""

    __tablename__ = "pefi_transaction_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("pefi_transactions.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    # Decided by sniffing the bytes (transaction_attachment_service), never taken from the upload.
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
