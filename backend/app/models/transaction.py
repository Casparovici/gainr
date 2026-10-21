import enum
from datetime import date as date_, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TransactionType(str, enum.Enum):
    BUY = "Buy"
    SELL = "Sell"
    DIVIDEND = "Dividend"
    INTEREST = "Interest"
    DEPOSIT = "Deposit"
    WITHDRAW = "Withdraw"
    BROKER_FEE = "Broker Fee"
    STAKING = "Staking"
    # Cash moving from one broker to another *within* the portfolio -- unlike Deposit/Withdraw
    # (money entering/leaving the portfolio entirely, which is what a gripr account transfer
    # mirrors as -- see docs/adr/0014), a Transfer nets to zero on total cash and never touches
    # net_invested_eur. It only re-attributes which broker's bucket holds the money, via
    # `broker` (source) and `to_broker` (destination).
    TRANSFER = "Transfer"


# Transaction types not tied to a specific asset (pure cash movements).
CASH_ONLY_TYPES = {
    TransactionType.INTEREST,
    TransactionType.DEPOSIT,
    TransactionType.WITHDRAW,
    TransactionType.BROKER_FEE,
    TransactionType.TRANSFER,
}

# Everything that moves cash except buying and selling positions: the ledger rows behind the Cash
# row's balance. A Dividend belongs to an asset but pays out as cash; Staking is a non-cash
# quantity increase, so it isn't here. A Transfer nets to zero on the total but moves money
# between brokers' buckets.
CASH_MOVEMENT_TYPES = CASH_ONLY_TYPES | {TransactionType.DIVIDEND}

NUMERIC = Numeric(20, 8)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Every transaction belongs to exactly one portfolio -- positions/cash/performance are all
    # derived per-portfolio, never across the whole table. See docs/adr/0019.
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    date: Mapped[date_] = mapped_column(Date, index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))

    quantity: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)  # native currency
    local_value: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)  # native currency
    fx_rate: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)  # native -> EUR
    value_eur: Mapped[Decimal] = mapped_column(NUMERIC, default=0)
    costs: Mapped[Decimal] = mapped_column(NUMERIC, default=0)
    total_eur: Mapped[Decimal] = mapped_column(NUMERIC, default=0)

    broker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Only set on a Transfer, where it's the destination -- `broker` is the source. Every other
    # type only ever has one broker involved, so this stays null for them.
    to_broker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Provenance for rows brought in by the xlsx import (e.g. "xlsx:Transaction:row45"), used
    # to make re-running the import idempotent without guessing at value-based duplicates —
    # the source sheet has no unique transaction id and legitimately contains same-day,
    # same-amount rows (e.g. two identical deposits). Null for transactions created in-app.
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    asset = relationship("Asset", back_populates="transactions")
