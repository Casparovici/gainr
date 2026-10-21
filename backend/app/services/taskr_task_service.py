"""taskr's own tasks: the rules for adding, changing and ticking one off, and their place on the
agenda next to the modules' items (the addendum on docs/adr/0038). Unlike a planned workout, an
open task stays overdue however long ago it was due: nothing else will ever close it."""

from datetime import date as date_, datetime

from sqlalchemy.orm import Session

from app.models.taskr_task import TaskrTask
from app.repositories import taskr_task_repo
from app.schemas.taskr import AgendaItemOut, AgendaSource
from app.services.errors import InvalidRequest

# Fields a null in an update leaves alone rather than clears: a task always has a title and a day.
_REQUIRED = ("title", "due_date")


def _clean(fields: dict) -> dict:
    fields = {k: v for k, v in fields.items() if not (k in _REQUIRED and v is None)}
    if "title" in fields:
        fields["title"] = fields["title"].strip()
        if not fields["title"]:
            raise InvalidRequest("A task needs a title")
    if "notes" in fields:
        fields["notes"] = (fields["notes"] or "").strip() or None
    return fields


def create_task(db: Session, fields: dict) -> TaskrTask:
    return taskr_task_repo.create_task(db, **_clean(fields))


def update_task(db: Session, task: TaskrTask, fields: dict) -> TaskrTask:
    return taskr_task_repo.update_task(db, task, **_clean(fields))


def set_completed(db: Session, task: TaskrTask, is_completed: bool, now: datetime) -> TaskrTask:
    """Ticking off stamps the moment; ticking an already-done task off again keeps the first
    stamp, and un-ticking (the undo) clears it."""
    if not is_completed:
        return taskr_task_repo.update_task(db, task, completed_at=None)
    if task.completed_at is None:
        return taskr_task_repo.update_task(db, task, completed_at=now)
    return task


def agenda_items(db: Session, date_to: date_, today: date_) -> list[AgendaItemOut]:
    return [
        AgendaItemOut(
            key=f"taskr:task:{t.id}",
            source=AgendaSource.TASKR,
            title=t.title,
            detail=t.notes,
            due_date=t.due_date,
            is_overdue=t.due_date < today,
            link=None,
            task_id=t.id,
        )
        for t in taskr_task_repo.list_open_until(db, date_to)
    ]
