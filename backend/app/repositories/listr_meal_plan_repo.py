from datetime import date as date_

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.listr_meal_plan import ListrMealPlan
from app.models.listr_recipe import ListrRecipe


def list_range(db: Session, date_from: date_, date_to: date_) -> list[ListrMealPlan]:
    query = (
        select(ListrMealPlan)
        .options(joinedload(ListrMealPlan.recipe))
        .where(ListrMealPlan.date >= date_from, ListrMealPlan.date <= date_to)
        .order_by(ListrMealPlan.date)
    )
    return list(db.execute(query).unique().scalars().all())


def list_all(db: Session) -> list[ListrMealPlan]:
    """Every meal-plan entry ever recorded, for the ICS feed -- unlike list_range, not scoped
    to a visible calendar window, so a subscribed Google Calendar carries the full history too."""
    query = select(ListrMealPlan).options(joinedload(ListrMealPlan.recipe)).order_by(ListrMealPlan.date)
    return list(db.execute(query).unique().scalars().all())


def get_by_date(db: Session, date: date_) -> ListrMealPlan | None:
    query = select(ListrMealPlan).options(joinedload(ListrMealPlan.recipe)).where(ListrMealPlan.date == date)
    return db.execute(query).unique().scalar_one_or_none()


def upsert(db: Session, date: date_, **fields) -> ListrMealPlan:
    """One row per date -- update it in place if it already exists, otherwise create it, so the
    weekplanner's day cells can always just PUT their current state without tracking whether
    the day had an entry yet."""
    entry = db.execute(select(ListrMealPlan).where(ListrMealPlan.date == date)).scalar_one_or_none()
    if entry is None:
        entry = ListrMealPlan(date=date, **fields)
        db.add(entry)
    else:
        for key, value in fields.items():
            setattr(entry, key, value)
    db.flush()
    return entry


def clear(db: Session, date: date_) -> bool:
    entry = db.execute(select(ListrMealPlan).where(ListrMealPlan.date == date)).scalar_one_or_none()
    if entry is None:
        return False
    db.delete(entry)
    db.flush()
    return True


def unlink_recipe(db: Session, recipe_id: int) -> None:
    """Called before a recipe is deleted -- its meal-plan history survives with a blank recipe
    instead of being deleted or blocking the delete, same "unlink, don't destroy" convention
    gripr uses when a category is deleted out from under its transactions."""
    entries = db.execute(select(ListrMealPlan).where(ListrMealPlan.recipe_id == recipe_id)).scalars().all()
    for entry in entries:
        entry.recipe_id = None
    db.flush()


def popular_recipes(db: Session, limit: int = 10) -> list[tuple[int, str, int]]:
    query = (
        select(ListrRecipe.id, ListrRecipe.title, func.count(ListrMealPlan.id).label("times_cooked"))
        .join(ListrMealPlan, ListrMealPlan.recipe_id == ListrRecipe.id)
        .where(ListrMealPlan.is_cooked.is_(True))
        .group_by(ListrRecipe.id, ListrRecipe.title)
        .order_by(func.count(ListrMealPlan.id).desc(), ListrRecipe.title)
        .limit(limit)
    )
    return [(row.id, row.title, row.times_cooked) for row in db.execute(query)]
