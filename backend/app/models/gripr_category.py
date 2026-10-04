import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GriprCategoryKind(str, enum.Enum):
    EXPENSE = "expense"
    INCOME = "income"


class GriprCategory(Base):
    __tablename__ = "pefi_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[GriprCategoryKind] = mapped_column(Enum(GriprCategoryKind))
    # Null = a top-level category (the only level budgets attach to). Set = a subcategory,
    # used for finer-grained tagging on transactions without multiplying budget lines.
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("pefi_categories.id"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # Null = derive a colour from the fixed categorical palette by alphabetical rank within the
    # kind (the long-standing default everywhere colour is shown). Set = the user overrode it.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # Only meaningful for top-level categories (parent_id is null) — the only ones shown as
    # orderable tiles on Budget. Compared only within the same kind.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Only meaningful on an EXPENSE category. When set, a transaction filed under this category
    # automatically nudges the linked account's balance (see gripr_transaction_service) --
    # meant for a loan-type account, e.g. a "Studieschuld" category linked to the loan of the
    # same name, so a repayment there also lowers what's still owed on the loan.
    linked_loan_account_id: Mapped[int | None] = mapped_column(ForeignKey("pefi_accounts.id"), nullable=True)

    parent = relationship("GriprCategory", remote_side=[id], back_populates="children")
    children = relationship("GriprCategory", back_populates="parent")
    transactions = relationship("GriprTransaction", back_populates="category")
    budgets = relationship("GriprBudget", back_populates="category")
    linked_loan_account = relationship("GriprAccount", foreign_keys=[linked_loan_account_id])
