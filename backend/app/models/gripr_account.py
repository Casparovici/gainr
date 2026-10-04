import enum
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GriprAccountType(str, enum.Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    CREDIT = "credit"
    LOAN = "loan"
    ASSET = "asset"


class GriprBalanceMode(str, enum.Enum):
    # Balance = opening_balance + sum of every transaction touching this account. Used for
    # accounts with real transaction activity (checking, savings, investment).
    TRANSACTIONAL = "transactional"
    # Balance is just `manual_balance`, edited directly. Used for loans/mortgages and
    # net-worth-only trackers (a car's value, home equity) that don't have a transaction feed —
    # the source ledger itself only ever updates these by hand, not via booked transactions.
    MANUAL = "manual"


class GriprAccount(Base):
    __tablename__ = "pefi_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    type: Mapped[GriprAccountType] = mapped_column(Enum(GriprAccountType))
    balance_mode: Mapped[GriprBalanceMode] = mapped_column(Enum(GriprBalanceMode))
    # Only meaningful for balance_mode=TRANSACTIONAL: the balance the account held before its
    # earliest imported transaction, so derived balance = opening_balance + ledger sum lands on
    # the real-world figure even when the imported history doesn't go back to account opening.
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    # Only meaningful for balance_mode=MANUAL — the account's current value, edited directly.
    manual_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    # Historical accounts (e.g. a since-closed bank account) stay for the transactions that
    # reference them but drop out of the default Accounts view.
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # User-controlled display order within the account's type group (lower first). Only ever
    # compared against other accounts of the same type, so values don't need to be globally
    # unique or contiguous across types.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Null = derive a colour from the account's type (the long-standing default everywhere
    # account colour is shown). Set = the user overrode it — e.g. a bank's own brand colour,
    # same override pattern as GriprCategory.color.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # A key into gripr_bank_logo_service.GRIPR_BANKS (e.g. "ing", "trading212"), or null for no
    # logo. A fixed, hand-picked catalog rather than a free-text/lookup-by-ticker system like
    # gainr's asset logos — see docs/adr/0010.
    bank_logo_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Set when this account is a virtual pot inside another one -- money set aside on paper
    # ("Onderhoud Auto", "Reservering Vakantie") that really sits in that account (Trade
    # Republic). A bank sees pot spending as the parent's own, and never sees money moving
    # between the parent and its pots; the bank sync and recurring rules rely on knowing which
    # is which. One level only: a pot can't hold pots. See docs/adr/0029's addendum.
    held_in_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_accounts.id", ondelete="SET NULL"), nullable=True
    )

    transactions = relationship(
        "GriprTransaction", back_populates="account", foreign_keys="GriprTransaction.account_id"
    )
