from datetime import date as date_
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GriprBudget(Base):
    __tablename__ = "pefi_budgets"
    __table_args__ = (UniqueConstraint("category_id", "month", name="uq_pefi_budget_category_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("pefi_categories.id"), index=True)
    # Always the first of the month — a budget covers a whole calendar month, never a range.
    month: Mapped[date_] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    category = relationship("GriprCategory", back_populates="budgets")
