from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.garden_area import GardenArea
from app.models.garden_care import GardenActionType, GardenCareLog, GardenCareSchedule, GardenScheduleFrequency
from app.models.garden_plant import GardenPlant, GardenPlantType
from app.models.trainr_workout import TrainrActivityType, TrainrWorkout
from app.routers import taskr as taskr_router
from app.schemas.taskr import AgendaSource
from app.services import taskr_agenda_service

TODAY = date(2026, 10, 14)


def add_plant(db, name="Tomato") -> GardenPlant:
    area = GardenArea(name="Greenhouse")
    db.add(area)
    db.flush()
    plant = GardenPlant(area_id=area.id, name=name, type=GardenPlantType.PLANT)
    db.add(plant)
    db.flush()
    return plant


def add_schedule(db, plant, start_date, action=GardenActionType.WATER, custom_label=None, is_active=True):
    schedule = GardenCareSchedule(
        plant_id=plant.id, action_type=action, custom_label=custom_label, interval_value=1,
        frequency=GardenScheduleFrequency.WEEKLY, start_date=start_date, is_active=is_active,
        created_at=datetime(2026, 1, 1),
    )
    db.add(schedule)
    db.flush()
    return schedule


def add_workout(db, day, activity=TrainrActivityType.RUNNING, completed=False, distance=None):
    workout = TrainrWorkout(activity_type=activity, date=day, is_completed=completed, distance_km=distance)
    db.add(workout)
    db.flush()
    return workout


def agenda(db, date_from=TODAY, date_to=date(2026, 10, 20)):
    return taskr_agenda_service.build_agenda(db, date_from, date_to, TODAY)


def test_an_empty_database_gives_an_empty_agenda(db_session):
    result = agenda(db_session)

    assert result.overdue == []
    assert result.days == []


def test_each_module_contributes_items_on_its_due_date(db_session):
    add_schedule(db_session, add_plant(db_session, "Tomato"), date(2026, 10, 15))
    add_workout(db_session, date(2026, 10, 16), distance=Decimal("8"))

    result = agenda(db_session)

    assert [d.date for d in result.days] == [date(2026, 10, 15), date(2026, 10, 16)]
    garden, run = (d.items[0] for d in result.days)
    assert (garden.source, garden.title) == (AgendaSource.GARDNR, "Water Tomato")
    assert (run.source, run.title, run.detail) == (AgendaSource.TRAINR, "Run", "8 km")


def test_items_due_before_the_range_are_listed_as_overdue(db_session):
    add_schedule(db_session, add_plant(db_session), date(2026, 10, 10))
    add_workout(db_session, date(2026, 10, 12))

    result = agenda(db_session)

    assert [(i.source, i.due_date, i.is_overdue) for i in result.overdue] == [
        (AgendaSource.GARDNR, date(2026, 10, 10), True),
        (AgendaSource.TRAINR, date(2026, 10, 12), True),
    ]
    assert result.days == []


def test_overdue_is_relative_to_the_start_of_the_range(db_session):
    add_workout(db_session, date(2026, 10, 16))

    result = agenda(db_session, date_from=date(2026, 10, 19), date_to=date(2026, 10, 25))

    assert [i.due_date for i in result.overdue] == [date(2026, 10, 16)]
    assert result.days == []


def test_items_after_the_range_are_left_out(db_session):
    add_schedule(db_session, add_plant(db_session), date(2026, 11, 1))
    add_workout(db_session, date(2026, 11, 2))

    result = agenda(db_session)

    assert result.overdue == [] and result.days == []


def test_a_logged_care_action_moves_its_next_due_date_off_the_agenda(db_session):
    plant = add_plant(db_session)
    add_schedule(db_session, plant, date(2026, 10, 10))
    db_session.add(GardenCareLog(plant_id=plant.id, action_type=GardenActionType.WATER, performed_on=TODAY))
    db_session.flush()

    result = agenda(db_session)

    assert result.overdue == []
    assert [d.date for d in result.days] == []  # next watering is a week out, past the range


def test_inactive_schedules_and_archived_plants_are_skipped(db_session):
    plant = add_plant(db_session)
    add_schedule(db_session, plant, date(2026, 10, 15), is_active=False)
    archived = add_plant(db_session, "Old")
    archived.is_archived = True
    add_schedule(db_session, archived, date(2026, 10, 15))

    assert agenda(db_session).days == []


def test_completed_workouts_and_workouts_long_past_are_not_tasks(db_session):
    add_workout(db_session, date(2026, 10, 15), completed=True)
    add_workout(db_session, date(2026, 8, 1))  # planned months ago, never ticked off

    result = agenda(db_session)

    assert result.overdue == [] and result.days == []


def test_other_care_actions_use_their_custom_label(db_session):
    add_schedule(
        db_session, add_plant(db_session, "Maple"), date(2026, 10, 15),
        action=GardenActionType.OTHER, custom_label="Check for aphids",
    )

    item = agenda(db_session).days[0].items[0]

    assert item.title == "Check for aphids: Maple"


def test_items_within_a_day_are_ordered_by_module(db_session):
    add_workout(db_session, date(2026, 10, 15))
    add_schedule(db_session, add_plant(db_session), date(2026, 10, 15))

    items = agenda(db_session).days[0].items

    assert [i.source for i in items] == [AgendaSource.GARDNR, AgendaSource.TRAINR]


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(taskr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_agenda_endpoint_returns_the_merged_shape(client, db_session):
    add_workout(db_session, date.today())

    body = client.get(
        "/api/taskr/agenda", params={"date_from": date.today().isoformat(), "date_to": date.today().isoformat()}
    ).json()

    assert body["overdue"] == []
    assert body["days"][0]["items"][0]["key"].startswith("trainr:workout:")


def test_agenda_endpoint_rejects_a_reversed_or_oversized_range(client):
    reversed_ = client.get("/api/taskr/agenda", params={"date_from": "2026-10-20", "date_to": "2026-10-14"})
    too_long = client.get("/api/taskr/agenda", params={"date_from": "2020-01-01", "date_to": "2026-10-14"})

    assert reversed_.status_code == 422
    assert too_long.status_code == 422
