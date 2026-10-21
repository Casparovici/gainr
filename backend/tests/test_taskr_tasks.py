from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.taskr_task import TaskrTask
from app.routers import taskr as taskr_router
from app.schemas.taskr import AgendaSource
from app.services import taskr_agenda_service, taskr_task_service

TODAY = date(2026, 10, 14)


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(taskr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def add_task(db, title="Bel de loodgieter", due=TODAY, notes=None, completed_at=None) -> TaskrTask:
    task = TaskrTask(title=title, due_date=due, notes=notes, completed_at=completed_at)
    db.add(task)
    db.flush()
    return task


# -- on the agenda ------------------------------------------------------------------------------


def test_an_open_task_is_on_the_agenda_on_its_day_with_its_notes(db_session):
    task = add_task(db_session, notes="lekkende kraan")

    agenda = taskr_agenda_service.build_agenda(db_session, TODAY, date(2026, 10, 20), today=TODAY)

    [item] = agenda.days[0].items
    assert item.source == AgendaSource.TASKR
    assert item.key == f"taskr:task:{task.id}"
    assert item.task_id == task.id
    assert item.link is None
    assert (item.title, item.detail, item.is_overdue) == ("Bel de loodgieter", "lekkende kraan", False)


def test_an_open_task_stays_overdue_however_long_ago_it_was_due(db_session):
    add_task(db_session, due=date(2026, 1, 5))

    agenda = taskr_agenda_service.build_agenda(db_session, TODAY, TODAY, today=TODAY)

    assert [i.title for i in agenda.overdue] == ["Bel de loodgieter"]
    assert agenda.overdue[0].is_overdue


def test_a_ticked_off_task_and_one_after_the_range_are_left_out(db_session):
    add_task(db_session, title="Gedaan", completed_at=datetime(2026, 10, 14, 9))
    add_task(db_session, title="Later", due=date(2026, 11, 1))

    agenda = taskr_agenda_service.build_agenda(db_session, TODAY, date(2026, 10, 20), today=TODAY)

    assert agenda.overdue == [] and agenda.days == []


def test_ticking_off_again_keeps_the_first_moment_and_undo_clears_it(db_session):
    task = add_task(db_session)
    first = datetime(2026, 10, 14, 9)

    taskr_task_service.set_completed(db_session, task, True, now=first)
    taskr_task_service.set_completed(db_session, task, True, now=datetime(2026, 10, 14, 10))
    assert task.completed_at == first

    taskr_task_service.set_completed(db_session, task, False, now=datetime(2026, 10, 14, 11))
    assert task.completed_at is None


# -- the endpoints ------------------------------------------------------------------------------


def test_a_task_is_added_trimmed_changed_and_deleted(client):
    created = client.post("/api/taskr/tasks", json={"title": "  Fietsband plakken ", "notes": "  ", "due_date": "2026-10-15"})
    assert created.status_code == 200, created.text
    body = created.json()
    assert (body["title"], body["notes"], body["completed_at"]) == ("Fietsband plakken", None, None)

    changed = client.put(f"/api/taskr/tasks/{body['id']}", json={"due_date": "2026-10-16", "notes": "achterband"}).json()
    assert (changed["title"], changed["due_date"], changed["notes"]) == ("Fietsband plakken", "2026-10-16", "achterband")

    assert client.delete(f"/api/taskr/tasks/{body['id']}").status_code == 204
    assert client.delete(f"/api/taskr/tasks/{body['id']}").status_code == 404


def test_a_task_is_ticked_off_and_back(client):
    task_id = client.post("/api/taskr/tasks", json={"title": "Belasting", "due_date": "2026-10-15"}).json()["id"]

    done = client.put(f"/api/taskr/tasks/{task_id}/completed", json={"is_completed": True}).json()
    assert done["completed_at"] is not None
    undone = client.put(f"/api/taskr/tasks/{task_id}/completed", json={"is_completed": False}).json()
    assert undone["completed_at"] is None


def test_a_blank_title_is_refused(client):
    assert client.post("/api/taskr/tasks", json={"title": "", "due_date": "2026-10-15"}).status_code == 422
    assert client.post("/api/taskr/tasks", json={"title": "   ", "due_date": "2026-10-15"}).status_code == 400
    task_id = client.post("/api/taskr/tasks", json={"title": "Iets", "due_date": "2026-10-15"}).json()["id"]
    assert client.put(f"/api/taskr/tasks/{task_id}", json={"title": "  "}).status_code == 400
    # A null title or day in an update leaves it alone.
    assert client.put(f"/api/taskr/tasks/{task_id}", json={"title": None, "due_date": None}).json()["title"] == "Iets"


def test_a_missing_task_is_a_404(client):
    assert client.put("/api/taskr/tasks/999", json={"title": "x"}).status_code == 404
    assert client.put("/api/taskr/tasks/999/completed", json={"is_completed": True}).status_code == 404
