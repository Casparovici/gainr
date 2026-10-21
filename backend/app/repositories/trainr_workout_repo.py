from datetime import date as date_

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.trainr_workout import TrainrActivityType, TrainrWorkout, TrainrWorkoutEntry


def _with_entries():
    return selectinload(TrainrWorkout.entries).joinedload(TrainrWorkoutEntry.exercise)


def list_range(
    db: Session,
    date_from: date_,
    date_to: date_,
    activity_type: TrainrActivityType | None = None,
    completed: bool | None = None,
) -> list[TrainrWorkout]:
    query = (
        select(TrainrWorkout)
        .options(_with_entries())
        .where(TrainrWorkout.date >= date_from, TrainrWorkout.date <= date_to)
        .order_by(TrainrWorkout.date, TrainrWorkout.id)
    )
    if activity_type is not None:
        query = query.where(TrainrWorkout.activity_type == activity_type)
    if completed is not None:
        query = query.where(TrainrWorkout.is_completed.is_(completed))
    return list(db.execute(query).scalars().all())


def list_completed_entries(db: Session) -> list[tuple[TrainrWorkoutEntry, date_]]:
    """Every exercise entry of a completed workout, newest workout first -- the input for the
    per-exercise "last time" and "best weight" figures."""
    query = (
        select(TrainrWorkoutEntry, TrainrWorkout.date)
        .join(TrainrWorkout, TrainrWorkout.id == TrainrWorkoutEntry.workout_id)
        .where(TrainrWorkout.is_completed.is_(True))
        .order_by(TrainrWorkout.date.desc(), TrainrWorkout.id.desc(), TrainrWorkoutEntry.sort_order)
    )
    return [(entry, day) for entry, day in db.execute(query).all()]


def get_workout(db: Session, workout_id: int) -> TrainrWorkout | None:
    query = select(TrainrWorkout).options(_with_entries()).where(TrainrWorkout.id == workout_id)
    return db.execute(query).scalar_one_or_none()


def create_workout(db: Session, entries: list[dict], **fields) -> TrainrWorkout:
    workout = TrainrWorkout(**fields)
    workout.entries = [TrainrWorkoutEntry(sort_order=i, **e) for i, e in enumerate(entries)]
    db.add(workout)
    db.flush()
    return workout


def update_workout(db: Session, workout: TrainrWorkout, entries: list[dict], **fields) -> TrainrWorkout:
    """Replaces the workout's fields and its whole entry list -- delete-orphan drops the old
    entries -- since the form always sends the full state."""
    for key, value in fields.items():
        setattr(workout, key, value)
    workout.entries = [TrainrWorkoutEntry(sort_order=i, **e) for i, e in enumerate(entries)]
    db.flush()
    return workout


def set_completed(db: Session, workout: TrainrWorkout, is_completed: bool) -> TrainrWorkout:
    workout.is_completed = is_completed
    db.flush()
    return workout


def delete_workout(db: Session, workout: TrainrWorkout) -> None:
    db.delete(workout)
    db.flush()


def existing_source_refs(db: Session, refs: set[str]) -> set[str]:
    if not refs:
        return set()
    query = select(TrainrWorkout.source_ref).where(TrainrWorkout.source_ref.in_(refs))
    return set(db.execute(query).scalars().all())


def list_completed(db: Session, activity_type: TrainrActivityType) -> list[TrainrWorkout]:
    """Every done workout of one activity, oldest first -- the overview's whole input."""
    query = (
        select(TrainrWorkout)
        .options(_with_entries())
        .where(TrainrWorkout.activity_type == activity_type, TrainrWorkout.is_completed.is_(True))
        .order_by(TrainrWorkout.date, TrainrWorkout.id)
    )
    return list(db.execute(query).scalars().all())
