from datetime import date as date_, timedelta

from sqlalchemy.orm import Session

from app.models.listr_leftover import ListrLeftover
from app.models.listr_meal_plan import ListrMealPlan
from app.repositories import listr_leftover_repo, listr_recipe_repo
from app.services.errors import NotFound

# How long a batch keeps when the reader doesn't say: a few days in the fridge, a few months frozen.
DEFAULT_KEEP_DAYS = {"fridge": 3, "freezer": 90}
LOCATIONS = tuple(DEFAULT_KEEP_DAYS)


class NoMealsLeft(Exception):
    """The leftover a day wants to eat has no meal left to take."""


def default_use_by(location: str, stored_on: date_) -> date_:
    return stored_on + timedelta(days=DEFAULT_KEEP_DAYS[location])


def create_leftover(
    db: Session,
    *,
    name: str,
    recipe_id: int | None,
    meals: int,
    servings_per_meal: int | None,
    location: str,
    stored_on: date_ | None,
    use_by: date_ | None,
    today: date_,
) -> ListrLeftover:
    """Stored today unless said otherwise, and kept as long as its location allows unless a
    use-by is given."""
    if recipe_id is not None and listr_recipe_repo.get_recipe(db, recipe_id) is None:
        raise NotFound("Recipe not found")
    stored_on = stored_on or today
    return listr_leftover_repo.create(
        db,
        name=name.strip(),
        recipe_id=recipe_id,
        meals=meals,
        servings_per_meal=servings_per_meal,
        location=location,
        stored_on=stored_on,
        use_by=use_by or default_use_by(location, stored_on),
    )


def update_leftover(leftover: ListrLeftover, fields: dict) -> ListrLeftover:
    """Name, location and use-by are required, so a null for one of them means "unchanged";
    servings per meal is optional, so null clears it."""
    for key, value in fields.items():
        if value is None and key != "servings_per_meal":
            continue
        setattr(leftover, key, value)
    return leftover


def adjust_meals(leftover: ListrLeftover, delta: int) -> None:
    """The +/- buttons: a delta, clamped at 0, same shape as the inventory count."""
    leftover.meals = max(0, leftover.meals + delta)


def sync_meal_plan_consumption(entry: ListrMealPlan, leftover: ListrLeftover | None) -> None:
    """Make the leftover's meal count agree with what the day now says. A meal is taken off when
    the day is marked cooked with a leftover on it, and given back if the day is un-cooked, switched
    to another leftover/recipe, or cleared -- `leftover_consumed` remembers whether this row has
    already taken one, so saving the same day twice never deducts twice. `entry.leftover_id` is
    already the new value; `leftover` is the row it points at (None when it points at nothing)."""
    wants_meal = leftover is not None and entry.is_cooked
    if entry.leftover_consumed and not wants_meal:
        # Still pointing at the leftover that gave the meal (a moved pointer was refunded by
        # refund_previous before this runs), so the meal goes back to it.
        leftover.meals += 1
        entry.leftover_consumed = False
    elif wants_meal and not entry.leftover_consumed:
        if leftover.meals < 1:
            raise NoMealsLeft(leftover.name)
        leftover.meals -= 1
        entry.leftover_consumed = True


def refund_previous(entry: ListrMealPlan, previous: ListrLeftover | None, new_leftover_id: int | None) -> None:
    """The day is about to point somewhere else: if it had eaten a meal from the old leftover, give
    that meal back first, so the sync above only ever deals with the new pointer."""
    if entry.leftover_consumed and previous is not None and previous.id != new_leftover_id:
        previous.meals += 1
        entry.leftover_consumed = False
