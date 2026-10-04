from datetime import date as date_
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gripr_savings_goal import GriprSavingsGoal


def list_goals_for_month(db: Session, month: date_) -> list[GriprSavingsGoal]:
    return list(db.execute(select(GriprSavingsGoal).where(GriprSavingsGoal.month == month)).scalars().all())


def get_goal(db: Session, account_id: int, month: date_) -> GriprSavingsGoal | None:
    query = select(GriprSavingsGoal).where(GriprSavingsGoal.account_id == account_id, GriprSavingsGoal.month == month)
    return db.execute(query).scalar_one_or_none()


def upsert_goal(db: Session, account_id: int, month: date_, amount) -> GriprSavingsGoal:
    existing = get_goal(db, account_id, month)
    if existing:
        existing.amount = amount
        db.flush()
        return existing
    goal = GriprSavingsGoal(account_id=account_id, month=month, amount=amount)
    db.add(goal)
    db.flush()
    return goal


def sum_goals_in_range(db: Session, account_id: int, month_from: date_, month_to: date_) -> Decimal:
    query = select(func.coalesce(func.sum(GriprSavingsGoal.amount), 0)).where(
        GriprSavingsGoal.account_id == account_id,
        GriprSavingsGoal.month >= month_from,
        GriprSavingsGoal.month <= month_to,
    )
    return db.execute(query).scalar_one()
