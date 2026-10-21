from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GriprDepreciation(Base):
    """How much of a transfer is a car (or other manually valued asset) losing value: a monthly
    transfer into the depreciation fund *is* the depreciation, so when it books, the asset's
    manual balance drops by this amount. A row belongs to a recurring rule (the plan) or to a
    booked transaction (what was applied, kept so an edit or delete reverses exactly that, even if
    the rule has changed since). See docs/adr/0034-gripr-depreciation.md."""

    __tablename__ = "pefi_depreciations"

    id: Mapped[int] = mapped_column(primary_key=True)
    recurring_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_recurring_transactions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_transactions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("pefi_accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    account = relationship("GriprAccount")
