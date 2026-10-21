from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.trainr_exercise import TrainrExercise
from app.models.trainr_workout import TrainrWorkoutEntry


def list_exercises(db: Session, include_archived: bool = False) -> list[TrainrExercise]:
    query = select(TrainrExercise).order_by(TrainrExercise.muscle_group, TrainrExercise.name)
    if not include_archived:
        query = query.where(TrainrExercise.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_exercise(db: Session, exercise_id: int) -> TrainrExercise | None:
    return db.get(TrainrExercise, exercise_id)


def get_by_name(db: Session, name: str) -> TrainrExercise | None:
    """Case-insensitive, so "dumbbell press" can't sit next to "Dumbbell press"."""
    query = select(TrainrExercise).where(func.lower(TrainrExercise.name) == name.lower())
    return db.execute(query).scalar_one_or_none()


def existing_ids(db: Session, exercise_ids: set[int]) -> set[int]:
    if not exercise_ids:
        return set()
    query = select(TrainrExercise.id).where(TrainrExercise.id.in_(exercise_ids))
    return set(db.execute(query).scalars().all())


def create_exercise(db: Session, **fields) -> TrainrExercise:
    exercise = TrainrExercise(**fields)
    db.add(exercise)
    db.flush()
    return exercise


def update_exercise(db: Session, exercise: TrainrExercise, **fields) -> TrainrExercise:
    # Present key means "apply this" -- callers pass model_dump(exclude_unset=True).
    for key, value in fields.items():
        setattr(exercise, key, value)
    db.flush()
    return exercise


def is_used(db: Session, exercise_id: int) -> bool:
    query = select(TrainrWorkoutEntry.id).where(TrainrWorkoutEntry.exercise_id == exercise_id).limit(1)
    return db.execute(query).first() is not None


def delete_exercise(db: Session, exercise: TrainrExercise) -> None:
    db.delete(exercise)
    db.flush()
