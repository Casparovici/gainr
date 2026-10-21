"""The exercise list's rules: every exercise has a name, no two share one, and an exercise a
workout used can only be archived, so the workout keeps naming what was done (ADR 0037). A linked
demo must exist in the catalogue (ADR 0040)."""

from sqlalchemy.orm import Session

from app.models.trainr_exercise import TrainrExercise
from app.repositories import trainr_exercise_repo
from app.services import trainr_exercise_demo_provider
from app.services.errors import Conflict
from app.services.trainr_workout_service import TrainrValidationError

# Fields a null in an update leaves alone rather than clears: none of them is optional.
_REQUIRED = ("muscle_group", "equipment", "is_archived")


def _checked_name(db: Session, name: str | None, exercise_id: int | None = None) -> str:
    name = (name or "").strip()
    if not name:
        raise TrainrValidationError("Name is required")
    clash = trainr_exercise_repo.get_by_name(db, name)
    if clash is not None and clash.id != exercise_id:
        raise Conflict("An exercise with this name already exists")
    return name


def _check_demo(demo_id: str | None) -> None:
    if demo_id is not None and trainr_exercise_demo_provider.get_demo(demo_id) is None:
        raise TrainrValidationError("Unknown exercise demo")


def create_exercise(db: Session, fields: dict) -> TrainrExercise:
    _check_demo(fields.get("demo_id"))
    return trainr_exercise_repo.create_exercise(db, **{**fields, "name": _checked_name(db, fields.get("name"))})


def update_exercise(db: Session, exercise: TrainrExercise, fields: dict) -> TrainrExercise:
    if "name" in fields:
        fields["name"] = _checked_name(db, fields["name"], exercise.id)
    _check_demo(fields.get("demo_id"))
    fields = {k: v for k, v in fields.items() if not (k in _REQUIRED and v is None)}
    return trainr_exercise_repo.update_exercise(db, exercise, **fields)


def delete_exercise(db: Session, exercise: TrainrExercise) -> None:
    if trainr_exercise_repo.is_used(db, exercise.id):
        raise Conflict("This exercise is used in a workout; archive it instead")
    trainr_exercise_repo.delete_exercise(db, exercise)
