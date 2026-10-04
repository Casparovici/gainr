import enum
from datetime import date as date_, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.gripr_transaction import GriprTransactionType

NUMERIC = Numeric(14, 2)


class GriprRecurrenceFrequency(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class GriprRecurringTransaction(Base):
    __tablename__ = "pefi_recurring_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[GriprTransactionType] = mapped_column(Enum(GriprTransactionType))
    # Always a positive magnitude, same convention as GriprTransaction.amount.
    amount: Mapped[Decimal] = mapped_column(NUMERIC)
    account_id: Mapped[int] = mapped_column(ForeignKey("pefi_accounts.id"), index=True)
    counter_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_accounts.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("pefi_categories.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    frequency: Mapped[GriprRecurrenceFrequency] = mapped_column(Enum(GriprRecurrenceFrequency))
    # Repeat every `interval` periods of `frequency` -- "every 2 months", "every 3 weeks".
    # >=1 is enforced at the schema/router layer, not a DB CHECK (SQLite has no easy retrofit
    # for one via Alembic without a table rebuild).
    interval: Mapped[int] = mapped_column(Integer, default=1)
    # The first occurrence, and the anchor for what day-of-month/week/year every later one
    # falls on.
    start_date: Mapped[date_] = mapped_column(Date)
    end_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    # The next occurrence not yet booked as a real transaction. There's no live scheduler, so
    # catching up after the app sat unused for a while just means looping this forward to
    # today the next time anyone reads the recurring list — see gripr_recurring_service.generate_due.
    next_due_date: Mapped[date_] = mapped_column(Date, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    account = relationship("GriprAccount", foreign_keys=[account_id])
    counter_account = relationship("GriprAccount", foreign_keys=[counter_account_id])
    category = relationship("GriprCategory")
