from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.garden_care import GardenCareLog, GardenCareSchedule

# -- care logs ------------------------------------------------------------------------------


def list_logs(db: Session, plant_id: int) -> list[GardenCareLog]:
    query = (
        select(GardenCareLog)
        .where(GardenCareLog.plant_id == plant_id)
        .order_by(GardenCareLog.performed_on.desc(), GardenCareLog.id.desc())
    )
    return list(db.execute(query).scalars().all())


def list_logs_for_plants(db: Session, plant_ids: list[int]) -> dict[int, list[GardenCareLog]]:
    """Batched `list_logs` for a whole plants list -- one query instead of one per plant."""
    if not plant_ids:
        return {}
    query = (
        select(GardenCareLog)
        .where(GardenCareLog.plant_id.in_(plant_ids))
        .order_by(GardenCareLog.performed_on.desc(), GardenCareLog.id.desc())
    )
    by_plant: dict[int, list[GardenCareLog]] = {pid: [] for pid in plant_ids}
    for log in db.execute(query).scalars().all():
        by_plant[log.plant_id].append(log)
    return by_plant


def get_log(db: Session, log_id: int) -> GardenCareLog | None:
    return db.get(GardenCareLog, log_id)


def create_log(db: Session, **fields) -> GardenCareLog:
    log = GardenCareLog(**fields)
    db.add(log)
    db.flush()
    return log


def update_log(db: Session, log: GardenCareLog, **fields) -> GardenCareLog:
    # Present key means "apply this", including an explicit None to clear custom_label/notes --
    # callers pass model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(log, key, value)
    db.flush()
    return log


def delete_log(db: Session, log: GardenCareLog) -> None:
    db.delete(log)
    db.flush()


# -- care schedules -------------------------------------------------------------------------


def list_schedules(db: Session, plant_id: int) -> list[GardenCareSchedule]:
    query = select(GardenCareSchedule).where(GardenCareSchedule.plant_id == plant_id).order_by(GardenCareSchedule.id)
    return list(db.execute(query).scalars().all())


def list_schedules_for_plants(db: Session, plant_ids: list[int]) -> dict[int, list[GardenCareSchedule]]:
    if not plant_ids:
        return {}
    query = select(GardenCareSchedule).where(GardenCareSchedule.plant_id.in_(plant_ids)).order_by(GardenCareSchedule.id)
    by_plant: dict[int, list[GardenCareSchedule]] = {pid: [] for pid in plant_ids}
    for schedule in db.execute(query).scalars().all():
        by_plant[schedule.plant_id].append(schedule)
    return by_plant


def get_schedule(db: Session, schedule_id: int) -> GardenCareSchedule | None:
    return db.get(GardenCareSchedule, schedule_id)


def create_schedule(db: Session, **fields) -> GardenCareSchedule:
    schedule = GardenCareSchedule(**fields)
    db.add(schedule)
    db.flush()
    return schedule


def update_schedule(db: Session, schedule: GardenCareSchedule, **fields) -> GardenCareSchedule:
    # Present key means "apply this", including an explicit None to clear custom_label/notes --
    # callers pass model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(schedule, key, value)
    db.flush()
    return schedule


def delete_schedule(db: Session, schedule: GardenCareSchedule) -> None:
    db.delete(schedule)
    db.flush()
