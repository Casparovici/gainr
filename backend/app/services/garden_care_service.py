"""Computes due dates for care schedules from a plant's own care-log history -- there's no
stored `next_due_date` to advance (contrast gripr's recurring transactions, which book a real
ledger row and so need a persistent cursor). A schedule's due date is just "last time this
action was logged, plus the interval", recomputed fresh on every read.
"""

from datetime import date as date_

from dateutil.relativedelta import relativedelta

from app.models.garden_care import GardenCareLog, GardenCareSchedule, GardenScheduleFrequency
from app.schemas.gardnr import GardenActionSummary

_UNIT = {
    GardenScheduleFrequency.DAILY: "days",
    GardenScheduleFrequency.WEEKLY: "weeks",
    GardenScheduleFrequency.MONTHLY: "months",
    GardenScheduleFrequency.YEARLY: "years",
}


def advance(frequency: GardenScheduleFrequency, from_date: date_, interval: int = 1) -> date_:
    return from_date + relativedelta(**{_UNIT[frequency]: interval})


def _last_performed(schedule: GardenCareSchedule, logs: list[GardenCareLog]) -> date_ | None:
    matching = [log.performed_on for log in logs if log.action_type == schedule.action_type]
    return max(matching, default=None)


def next_due(schedule: GardenCareSchedule, logs: list[GardenCareLog]) -> date_:
    """The latest matching log plus the interval. A user-picked `start_date` is the first
    occurrence and nothing comes due before it -- a log from before then can push the date later
    but not earlier. Without one, the schedule's creation date anchors a never-logged action."""
    last = _last_performed(schedule, logs)
    if schedule.start_date is not None:
        if last is None:
            return schedule.start_date
        return max(schedule.start_date, advance(schedule.frequency, last, schedule.interval_value))
    base = last or schedule.created_at.date()
    return advance(schedule.frequency, base, schedule.interval_value)


def latest_action(logs: list[GardenCareLog]) -> GardenActionSummary | None:
    if not logs:
        return None
    latest = logs[0]  # callers pass logs already ordered performed_on desc, id desc
    return GardenActionSummary(action_type=latest.action_type, custom_label=latest.custom_label, date=latest.performed_on)


def scheduled_actions(
    schedules: list[GardenCareSchedule], logs: list[GardenCareLog], today: date_ | None = None
) -> list[GardenActionSummary]:
    """Every active schedule's next occurrence, soonest first -- what Vandaag needs for a plant
    with two things due at once, where `soonest_due_action` would only ever name one of them."""
    actions = []
    for s in schedules:
        if not s.is_active:
            continue
        due = next_due(s, logs)
        actions.append(
            GardenActionSummary(
                schedule_id=s.id,
                action_type=s.action_type,
                custom_label=s.custom_label,
                date=due,
                is_overdue=is_overdue(due, today),
            )
        )
    return sorted(actions, key=lambda a: a.date)


def soonest_due_action(
    schedules: list[GardenCareSchedule], logs: list[GardenCareLog], today: date_ | None = None
) -> GardenActionSummary | None:
    """The single most urgent scheduled action for a plant -- what a hover card or the Plants
    list actually wants, rather than every schedule's own due date."""
    actions = scheduled_actions(schedules, logs, today)
    return actions[0] if actions else None


def is_overdue(due_date: date_, today: date_ | None = None) -> bool:
    return due_date <= (today or date_.today())
