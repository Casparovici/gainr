from datetime import date, datetime

from app.models.garden_care import GardenActionType, GardenCareLog, GardenCareSchedule, GardenScheduleFrequency
from app.services import garden_care_service


def make_schedule(action_type=GardenActionType.WATER, interval_value=3, frequency=GardenScheduleFrequency.DAILY, is_active=True, created_at=None, start_date=None):
    return GardenCareSchedule(
        id=1,
        plant_id=1,
        action_type=action_type,
        interval_value=interval_value,
        frequency=frequency,
        is_active=is_active,
        start_date=start_date,
        created_at=created_at or datetime(2026, 1, 1),
    )


def make_log(action_type=GardenActionType.WATER, performed_on=date(2026, 1, 1)):
    return GardenCareLog(plant_id=1, action_type=action_type, performed_on=performed_on)


def test_next_due_falls_back_to_schedule_creation_when_never_logged():
    schedule = make_schedule(created_at=datetime(2026, 1, 1))

    due = garden_care_service.next_due(schedule, logs=[])

    assert due == date(2026, 1, 4)


def test_next_due_advances_from_the_latest_matching_log():
    schedule = make_schedule(interval_value=3, frequency=GardenScheduleFrequency.DAILY)
    logs = [make_log(performed_on=date(2026, 1, 5)), make_log(performed_on=date(2026, 1, 10))]

    due = garden_care_service.next_due(schedule, logs)

    assert due == date(2026, 1, 13)  # latest log (Jan 10) + 3 days, not the earlier one


def test_next_due_ignores_logs_of_a_different_action_type():
    schedule = make_schedule(action_type=GardenActionType.WATER, interval_value=1, frequency=GardenScheduleFrequency.WEEKLY)
    logs = [make_log(action_type=GardenActionType.PRUNE, performed_on=date(2026, 1, 10))]

    due = garden_care_service.next_due(schedule, logs)

    # No WATER log exists, so it falls back to the schedule's own creation date, not the
    # unrelated PRUNE log.
    assert due == date(2026, 1, 8)


def test_next_due_is_the_start_date_itself_when_never_logged():
    schedule = make_schedule(created_at=datetime(2026, 1, 1), start_date=date(2026, 3, 1))

    assert garden_care_service.next_due(schedule, logs=[]) == date(2026, 3, 1)  # not Mar 4: it's the first occurrence


def test_next_due_with_a_start_date_advances_from_a_log_on_or_after_it():
    schedule = make_schedule(interval_value=3, start_date=date(2026, 3, 1))

    assert garden_care_service.next_due(schedule, [make_log(performed_on=date(2026, 3, 2))]) == date(2026, 3, 5)


def test_next_due_never_comes_before_the_start_date():
    # Watered Jan 10, but the schedule was set to start Mar 1 -- Jan 13 would read as long overdue.
    schedule = make_schedule(interval_value=3, start_date=date(2026, 3, 1))

    assert garden_care_service.next_due(schedule, [make_log(performed_on=date(2026, 1, 10))]) == date(2026, 3, 1)


def test_next_due_lets_a_log_just_before_the_start_date_push_the_first_occurrence_later():
    # Watered Feb 28 for a schedule starting Mar 1: watering again the very next day is wrong.
    schedule = make_schedule(interval_value=3, start_date=date(2026, 3, 1))

    assert garden_care_service.next_due(schedule, [make_log(performed_on=date(2026, 2, 28))]) == date(2026, 3, 3)


def test_advance_handles_every_frequency_unit():
    d = date(2026, 1, 1)
    assert garden_care_service.advance(GardenScheduleFrequency.DAILY, d, 5) == date(2026, 1, 6)
    assert garden_care_service.advance(GardenScheduleFrequency.WEEKLY, d, 2) == date(2026, 1, 15)
    assert garden_care_service.advance(GardenScheduleFrequency.MONTHLY, d, 1) == date(2026, 2, 1)
    assert garden_care_service.advance(GardenScheduleFrequency.YEARLY, d, 1) == date(2027, 1, 1)


def test_is_overdue():
    assert garden_care_service.is_overdue(date(2026, 1, 1), today=date(2026, 1, 1)) is True
    assert garden_care_service.is_overdue(date(2026, 1, 1), today=date(2025, 12, 31)) is False


def test_soonest_due_action_picks_the_earliest_across_active_schedules_only():
    soon = GardenCareSchedule(
        id=1, plant_id=1, action_type=GardenActionType.WATER, interval_value=1,
        frequency=GardenScheduleFrequency.DAILY, is_active=True, created_at=datetime(2026, 1, 1),
    )
    later = GardenCareSchedule(
        id=2, plant_id=1, action_type=GardenActionType.PRUNE, interval_value=1,
        frequency=GardenScheduleFrequency.YEARLY, is_active=True, created_at=datetime(2026, 1, 1),
    )
    paused_but_earlier = GardenCareSchedule(
        id=3, plant_id=1, action_type=GardenActionType.TRIM, interval_value=1,
        frequency=GardenScheduleFrequency.DAILY, is_active=False, created_at=datetime(2025, 1, 1),
    )

    result = garden_care_service.soonest_due_action([soon, later, paused_but_earlier], logs=[])

    assert result is not None
    assert result.action_type == GardenActionType.WATER  # Jan 2 beats Jan 2027; the paused one is excluded entirely


def test_soonest_due_action_is_none_when_no_active_schedules():
    assert garden_care_service.soonest_due_action([], logs=[]) is None


def test_latest_action_reads_the_first_log_assuming_caller_ordering():
    logs = [make_log(performed_on=date(2026, 1, 10)), make_log(performed_on=date(2026, 1, 1))]

    result = garden_care_service.latest_action(logs)

    assert result is not None
    assert result.date == date(2026, 1, 10)


def test_latest_action_is_none_with_no_logs():
    assert garden_care_service.latest_action([]) is None


def test_scheduled_actions_lists_every_active_schedule_soonest_first():
    water = make_schedule(action_type=GardenActionType.WATER, interval_value=3, frequency=GardenScheduleFrequency.DAILY)
    prune = make_schedule(action_type=GardenActionType.PRUNE, interval_value=1, frequency=GardenScheduleFrequency.DAILY)
    paused = make_schedule(action_type=GardenActionType.FERTILIZE, interval_value=1, frequency=GardenScheduleFrequency.DAILY, is_active=False)
    water.id, prune.id, paused.id = 1, 2, 3

    actions = garden_care_service.scheduled_actions([water, prune, paused], logs=[], today=date(2026, 1, 3))

    assert [(a.schedule_id, a.action_type, a.date) for a in actions] == [
        (2, GardenActionType.PRUNE, date(2026, 1, 2)),
        (1, GardenActionType.WATER, date(2026, 1, 4)),
    ]
    assert [a.is_overdue for a in actions] == [True, False]


def test_soonest_due_action_is_the_first_scheduled_action():
    water = make_schedule(action_type=GardenActionType.WATER, interval_value=3)
    prune = make_schedule(action_type=GardenActionType.PRUNE, interval_value=1)

    assert garden_care_service.soonest_due_action([water, prune], logs=[]) == garden_care_service.scheduled_actions([water, prune], logs=[])[0]

