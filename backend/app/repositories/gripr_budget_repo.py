from datetime import date as date_

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.gripr_budget import GriprBudget


def list_budgets_for_month(db: Session, month: date_) -> list[GriprBudget]:
    return list(db.execute(select(GriprBudget).where(GriprBudget.month == month)).scalars().all())


def get_budget(db: Session, category_id: int, month: date_) -> GriprBudget | None:
    query = select(GriprBudget).where(GriprBudget.category_id == category_id, GriprBudget.month == month)
    return db.execute(query).scalar_one_or_none()


def upsert_budget(db: Session, category_id: int, month: date_, amount) -> GriprBudget:
    existing = get_budget(db, category_id, month)
    if existing:
        existing.amount = amount
        db.flush()
        return existing
    budget = GriprBudget(category_id=category_id, month=month, amount=amount)
    db.add(budget)
    db.flush()
    return budget


def delete_for_categories(db: Session, category_ids: list[int]) -> None:
    db.execute(delete(GriprBudget).where(GriprBudget.category_id.in_(category_ids)))
    db.flush()
