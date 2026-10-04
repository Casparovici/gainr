import enum
from datetime import date as date_, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

NUMERIC = Numeric(14, 2)


class GriprTransactionType(str, enum.Enum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    # Money coming back that undoes part of an expense -- a friend paying their half of a
    # dinner, a shop refund. Enters `account_id` like income, but is filed under an *expense*
    # category and nets against that category's spend instead of counting as earnings.
    # See docs/adr/0023.
    REFUND = "refund"


class GriprTransaction(Base):
    __tablename__ = "pefi_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date_] = mapped_column(Date, index=True)
    type: Mapped[GriprTransactionType] = mapped_column(Enum(GriprTransactionType))
    # Always a positive magnitude — direction comes from `type`, not the sign.
    amount: Mapped[Decimal] = mapped_column(NUMERIC)
    # The paying account (expense), receiving account (income), or source account (transfer).
    account_id: Mapped[int] = mapped_column(ForeignKey("pefi_accounts.id"), index=True)
    # Only set for type=TRANSFER: the destination account.
    counter_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_accounts.id"), nullable=True, index=True
    )
    # Only set for type in (EXPENSE, INCOME) — a transfer moves money, it doesn't spend/earn it.
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_categories.id"), nullable=True, index=True
    )
    # Only set for type=REFUND: the expense this money came back for. Optional (a shop refund
    # whose purchase predates the ledger has nothing to point at). When set, the refund takes
    # the expense's category and counts toward spend in the expense's period, not its own --
    # a Tikkie arriving on the 2nd still lowers what last month's dinner cost.
    refund_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_transactions.id"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Only for type=EXPENSE: how much of it the reader fronted for others and expects back (a
    # restaurant bill paid for the table), and from whom. Spending counts only the reader's own
    # share from the start; what's still to come back is listed as owed to them until refunds
    # linked to this expense cover it or the rest is written off. See docs/adr/0032.
    expected_back: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)
    expected_from: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Provenance for rows brought in by the CSV import (e.g. "gripr_csv:row:412"), used to make
    # re-running the import idempotent — mirrors how the gainr ledger import works, for the
    # same reason: the source export has no stable id of its own to key off.
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    # Whether this row's side effects -- a loan-linked category's balance nudge, a portfolio-linked
    # transfer's mirror in gainr -- have been applied. A recurring occurrence pre-booked ahead of
    # its date has not (they're applied once it's due), and an edit or delete must only ever
    # reverse what was actually applied: reversing an effect that never happened is how deleting a
    # pre-booked Studieschuld occurrence once undid a real repayment. See docs/adr/0020.
    effects_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    account = relationship("GriprAccount", back_populates="transactions", foreign_keys=[account_id])
    counter_account = relationship("GriprAccount", foreign_keys=[counter_account_id])
    category = relationship("GriprCategory", back_populates="transactions")
    refund_of = relationship("GriprTransaction", remote_side=[id], foreign_keys=[refund_of_id])
