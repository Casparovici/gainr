from datetime import date as date_

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.taskr_task import TaskrTask


def list_open_until(db: Session, date_to: date_) -> list[TaskrTask]:
    """Tasks not ticked off and due on or before `date_to`, however long ago."""
    query = (
        select(TaskrTask)
        .where(TaskrTask.completed_at.is_(None), TaskrTask.due_date <= date_to)
        .order_by(TaskrTask.due_date, TaskrTask.id)
    )
    return list(db.execute(query).scalars().all())


def get_task(db: Session, task_id: int) -> TaskrTask | None:
    return db.get(TaskrTask, task_id)


def create_task(db: Session, **fields) -> TaskrTask:
    task = TaskrTask(**fields)
    db.add(task)
    db.flush()
    return task


def update_task(db: Session, task: TaskrTask, **fields) -> TaskrTask:
    # Present key means "apply this" -- callers pass model_dump(exclude_unset=True).
    for key, value in fields.items():
        setattr(task, key, value)
    db.flush()
    return task


def delete_task(db: Session, task: TaskrTask) -> None:
    db.delete(task)
    db.flush()
