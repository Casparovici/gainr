from datetime import date as date_, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.taskr_task import TaskrTask
from app.repositories import taskr_task_repo
from app.routers.errors import domain_errors
from app.schemas.taskr import AgendaOut, TaskrTaskCompletedIn, TaskrTaskCreate, TaskrTaskOut, TaskrTaskUpdate, TodayOut
from app.services import taskr_agenda_service, taskr_task_service, taskr_today_service

router = APIRouter(prefix="/api/taskr", tags=["taskr"])

# An agenda is a day, a week or a month; the cap keeps a typo'd range from walking years of
# recurring schedules.
MAX_RANGE_DAYS = 366


@router.get("/today", response_model=TodayOut)
def get_today(portfolio_id: int | None = None, db: Session = Depends(get_db)):
    """Vandaag, the start screen: today's agenda and what waits in each module. `portfolio_id`
    picks the gainr portfolio shown (the reader's current one); without it, the first."""
    return taskr_today_service.build_today(db, today=date_.today(), portfolio_id=portfolio_id)


@router.get("/agenda", response_model=AgendaOut)
def get_agenda(date_from: date_, date_to: date_, db: Session = Depends(get_db)):
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to is before date_from")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Date range too long")
    return taskr_agenda_service.build_agenda(db, date_from, date_to, today=date_.today())


# -- taskr's own tasks ---------------------------------------------------------------------------


def _get_task(db: Session, task_id: int) -> TaskrTask:
    task = taskr_task_repo.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks", response_model=TaskrTaskOut)
def create_task(payload: TaskrTaskCreate, db: Session = Depends(get_db)):
    with domain_errors():
        task = taskr_task_service.create_task(db, payload.model_dump())
    db.commit()
    return task


@router.put("/tasks/{task_id}", response_model=TaskrTaskOut)
def update_task(task_id: int, payload: TaskrTaskUpdate, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    with domain_errors():
        taskr_task_service.update_task(db, task, payload.model_dump(exclude_unset=True))
    db.commit()
    return task


@router.put("/tasks/{task_id}/completed", response_model=TaskrTaskOut)
def set_task_completed(task_id: int, payload: TaskrTaskCompletedIn, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    taskr_task_service.set_completed(db, task, payload.is_completed, now=datetime.now())
    db.commit()
    return task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    taskr_task_repo.delete_task(db, _get_task(db, task_id))
    db.commit()
