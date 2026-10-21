"""taskr's agenda: one date-ordered list of what's due across the modules. Derived on every
request -- the modules own their tasks and their completion, taskr only asks each module's agenda
service what is due and merges the answers (docs/adr/0038). taskr's own tasks join through the
same signature (the addendum on 0038)."""

from collections import defaultdict
from datetime import date as date_

from sqlalchemy.orm import Session

from app.schemas.taskr import AgendaDayOut, AgendaItemOut, AgendaOut
from app.services import garden_agenda_service, taskr_task_service, trainr_agenda_service

# Every module contributes through the same signature: (db, date_to, today) -> items due on or
# before date_to, including anything overdue.
_PROVIDERS = (garden_agenda_service, trainr_agenda_service, taskr_task_service)


def build_agenda(db: Session, date_from: date_, date_to: date_, today: date_) -> AgendaOut:
    items: list[AgendaItemOut] = []
    for provider in _PROVIDERS:
        items.extend(provider.agenda_items(db, date_to, today))

    # Overdue is relative to the start of the requested range, not to today, so a week view
    # starting next Monday still lists what's slipped before it.
    overdue = sorted((i for i in items if i.due_date < date_from), key=lambda i: (i.due_date, i.title))
    by_day: dict[date_, list[AgendaItemOut]] = defaultdict(list)
    for item in items:
        if date_from <= item.due_date <= date_to:
            by_day[item.due_date].append(item)
    days = [
        AgendaDayOut(date=day, items=sorted(by_day[day], key=lambda i: (i.source.value, i.title)))
        for day in sorted(by_day)
    ]
    return AgendaOut(date_from=date_from, date_to=date_to, overdue=overdue, days=days)
