from datetime import date as date_

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.listr_leftover import ListrLeftover
from app.models.listr_meal_plan import ListrMealPlan


def list_available(db: Session) -> list[ListrLeftover]:
    """Leftovers with a meal left, soonest use-by first -- what to eat up next."""
    query = select(ListrLeftover).where(ListrLeftover.meals > 0).order_by(ListrLeftover.use_by, ListrLeftover.name)
    return list(db.execute(query).scalars().all())


def get(db: Session, leftover_id: int) -> ListrLeftover | None:
    return db.get(ListrLeftover, leftover_id)


def create(db: Session, **fields) -> ListrLeftover:
    leftover = ListrLeftover(**fields)
    db.add(leftover)
    db.flush()
    return leftover


def delete(db: Session, leftover: ListrLeftover) -> None:
    """Weekplanner days that ate it keep their history with a blank leftover, the same "unlink,
    don't destroy" convention a deleted recipe follows."""
    entries = db.execute(select(ListrMealPlan).where(ListrMealPlan.leftover_id == leftover.id)).scalars().all()
    for entry in entries:
        entry.leftover_id = None
        entry.leftover_consumed = False
    db.delete(leftover)
    db.flush()


def unlink_recipe(db: Session, recipe_id: int) -> None:
    for leftover in db.execute(select(ListrLeftover).where(ListrLeftover.recipe_id == recipe_id)).scalars().all():
        leftover.recipe_id = None
    db.flush()


def expiring_by(db: Session, day: date_) -> list[ListrLeftover]:
    query = select(ListrLeftover).where(ListrLeftover.meals > 0, ListrLeftover.use_by <= day)
    return list(db.execute(query).scalars().all())
