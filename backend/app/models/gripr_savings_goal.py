from datetime import date as date_
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GriprSavingsGoal(Base):
    __tablename__ = "pefi_savings_goals"
    __table_args__ = (UniqueConstraint("account_id", "month", name="uq_gripr_savings_goal_account_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Only meaningful for a savings- or investment-type account -- enforced in the router, not
    # here, since it needs a database lookup (same pattern as linked_loan_account_id).
    account_id: Mapped[int] = mapped_column(ForeignKey("pefi_accounts.id"), index=True)
    # Always the first of the period -- a goal covers a whole period, never a range. See
    # GriprBudget for the same convention.
    month: Mapped[date_] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    account = relationship("GriprAccount")
