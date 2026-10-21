"""Planning a weekplanner day: a recipe or a leftover (never both), and keeping a leftover's
meal count in step with the day eating from it (see listr_leftover_service, ADR 0036)."""

from datetime import date as date_, datetime, timedelta

from icalendar import Calendar, Event
from sqlalchemy.orm import Session

from app.models.listr_meal_plan import ListrMealPlan
from app.repositories import listr_leftover_repo, listr_meal_plan_repo, listr_recipe_repo
from app.services import listr_leftover_service
from app.services.errors import Conflict, InvalidRequest, NotFound


def set_day(
    db: Session, day: date_, *, recipe_id: int | None, leftover_id: int | None, is_cooked: bool, notes: str | None
) -> ListrMealPlan:
    """Raises listr_leftover_service.NoMealsLeft when a cooked day would eat from an empty
    leftover; the caller rolls back, since the day row has already been written by then."""
    if recipe_id is not None and listr_recipe_repo.get_recipe(db, recipe_id) is None:
        raise NotFound("Recipe not found")
    if recipe_id is not None and leftover_id is not None:
        raise InvalidRequest("A day carries a recipe or a leftover, not both")
    leftover = None
    if leftover_id is not None:
        leftover = listr_leftover_repo.get(db, leftover_id)
        if leftover is None:
            raise NotFound("Leftover not found")

    existing = listr_meal_plan_repo.get_by_date(db, day)
    if existing is not None:
        listr_leftover_service.refund_previous(existing, existing.leftover, leftover_id)
    entry = listr_meal_plan_repo.upsert(
        db, day, recipe_id=recipe_id, leftover_id=leftover_id, is_cooked=is_cooked, notes=notes
    )
    listr_leftover_service.sync_meal_plan_consumption(entry, leftover)
    return entry


def clear_day(db: Session, day: date_) -> None:
    """A cleared day gives back the leftover meal it had eaten."""
    existing = listr_meal_plan_repo.get_by_date(db, day)
    if existing is not None:
        listr_leftover_service.refund_previous(existing, existing.leftover, None)
    listr_meal_plan_repo.clear(db, day)


def move_day(db: Session, day: date_, to: date_) -> ListrMealPlan:
    """Plans what's on `day` for `to` instead. The target must be free: replacing a planned day
    would silently throw its recipe away (and give back or lose a leftover meal)."""
    entry = listr_meal_plan_repo.get_by_date(db, day)
    if entry is None:
        raise NotFound("Nothing is planned on that day")
    if to == day:
        return entry
    if listr_meal_plan_repo.get_by_date(db, to) is not None:
        raise Conflict("Something is already planned on that day")
    listr_meal_plan_repo.move(db, entry, to)
    return entry


def calendar_feed(db: Session, now: datetime) -> bytes:
    """Every planned day as an all-day event, for subscribing the weekplanner in another
    calendar (ADR 0007): the recipe or leftover as the title, ✓ once cooked, notes as the
    description. Built fresh per request, so `now` is each event's DTSTAMP -- RFC 5545 requires
    one, and Google Calendar silently drops events without it."""
    cal = Calendar()
    cal.add("prodid", "-//gainr//listr weekplanner//NL")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Weekplanner")
    for entry in listr_meal_plan_repo.list_all(db):
        title = entry.recipe.title if entry.recipe else (entry.leftover.name if entry.leftover else entry.notes)
        if not title:
            continue  # defensive -- upsert never leaves a row with neither recipe nor notes
        event = Event()
        event.add("summary", f"✓ {title}" if entry.is_cooked else title)
        if (entry.recipe or entry.leftover) and entry.notes:
            event.add("description", entry.notes)
        event.add("dtstart", entry.date)
        event.add("dtend", entry.date + timedelta(days=1))
        event.add("dtstamp", now)
        event.add("uid", f"grecipe-meal-{entry.date.isoformat()}@ipper")
        cal.add_component(event)
    return cal.to_ical()
