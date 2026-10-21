from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date as date_

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.trainr_workout import TrainrActivityType
from app.repositories import trainr_exercise_repo, trainr_workout_repo
from app.schemas.trainr import (
    TrainrExerciseCreate,
    TrainrExerciseDemoOut,
    TrainrExerciseOut,
    TrainrExerciseUpdate,
    TrainrOverviewOut,
    TrainrSummaryOut,
    TrainrWorkoutCompletedIn,
    TrainrWorkoutIn,
    TrainrWorkoutOut,
)
from app.routers.errors import domain_errors
from app.services import (
    trainr_exercise_demo_provider,
    trainr_exercise_service,
    trainr_overview_service,
    trainr_workout_service,
)
from app.services.trainr_workout_service import TrainrValidationError

router = APIRouter(prefix="/api/trainr", tags=["trainr"])

# A history or planner request never needs more than a few years; the cap keeps a typo'd range
# from loading every workout ever into one response.
MAX_RANGE_DAYS = 3 * 366


def _check_range(date_from: date_, date_to: date_) -> None:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to is before date_from")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Date range too long")


def _exercise_out(db: Session, exercise_id: int) -> TrainrExerciseOut:
    rows = trainr_workout_service.list_exercises_with_stats(db, include_archived=True)
    return next(r for r in rows if r.id == exercise_id)


# -- exercises ------------------------------------------------------------------------------


@router.get("/exercises", response_model=list[TrainrExerciseOut])
def list_exercises(include_archived: bool = False, db: Session = Depends(get_db)):
    return trainr_workout_service.list_exercises_with_stats(db, include_archived=include_archived)


@contextmanager
def _exercise_errors() -> Iterator[None]:
    """trainr answers a field that doesn't fit with a 422, like its workouts do."""
    with domain_errors():
        try:
            yield
        except TrainrValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/exercises", response_model=TrainrExerciseOut)
def create_exercise(payload: TrainrExerciseCreate, db: Session = Depends(get_db)):
    with _exercise_errors():
        exercise = trainr_exercise_service.create_exercise(db, payload.model_dump())
    db.commit()
    return _exercise_out(db, exercise.id)


@router.put("/exercises/{exercise_id}", response_model=TrainrExerciseOut)
def update_exercise(exercise_id: int, payload: TrainrExerciseUpdate, db: Session = Depends(get_db)):
    exercise = trainr_exercise_repo.get_exercise(db, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    with _exercise_errors():
        trainr_exercise_service.update_exercise(db, exercise, payload.model_dump(exclude_unset=True))
    db.commit()
    return _exercise_out(db, exercise_id)


@router.delete("/exercises/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: int, db: Session = Depends(get_db)):
    exercise = trainr_exercise_repo.get_exercise(db, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    with _exercise_errors():
        trainr_exercise_service.delete_exercise(db, exercise)
    db.commit()


@router.get("/exercise-demos", response_model=list[TrainrExerciseDemoOut])
def search_exercise_demos(q: str = Query(max_length=100), limit: int = Query(default=20, ge=1, le=50)):
    """The how-to demos to link an exercise to (ADR 0040), searched by name."""
    return [demo.model_dump() for demo in trainr_exercise_demo_provider.search(q, limit)]


# -- workouts -------------------------------------------------------------------------------


@router.get("/workouts", response_model=list[TrainrWorkoutOut])
def list_workouts(
    date_from: date_,
    date_to: date_,
    activity_type: TrainrActivityType | None = None,
    completed: bool | None = None,
    db: Session = Depends(get_db),
):
    _check_range(date_from, date_to)
    workouts = trainr_workout_repo.list_range(db, date_from, date_to, activity_type=activity_type, completed=completed)
    return [trainr_workout_service.to_out(w) for w in workouts]


@router.get("/summary", response_model=TrainrSummaryOut)
def get_summary(date_from: date_, date_to: date_, db: Session = Depends(get_db)):
    _check_range(date_from, date_to)
    return trainr_workout_service.summary(db, date_from, date_to)


@router.get("/overview", response_model=TrainrOverviewOut)
def get_overview(activity_type: TrainrActivityType, db: Session = Depends(get_db)):
    workouts = trainr_workout_repo.list_completed(db, activity_type)
    return trainr_overview_service.overview(activity_type, workouts, date_.today())


@router.post("/workouts", response_model=TrainrWorkoutOut)
def create_workout(payload: TrainrWorkoutIn, db: Session = Depends(get_db)):
    try:
        workout = trainr_workout_service.create_workout(db, payload)
    except TrainrValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return trainr_workout_service.to_out(trainr_workout_repo.get_workout(db, workout.id))


@router.get("/workouts/{workout_id}", response_model=TrainrWorkoutOut)
def get_workout(workout_id: int, db: Session = Depends(get_db)):
    workout = trainr_workout_repo.get_workout(db, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return trainr_workout_service.to_out(workout)


@router.put("/workouts/{workout_id}", response_model=TrainrWorkoutOut)
def update_workout(workout_id: int, payload: TrainrWorkoutIn, db: Session = Depends(get_db)):
    workout = trainr_workout_repo.get_workout(db, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    try:
        trainr_workout_service.update_workout(db, workout, payload)
    except TrainrValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.expire_all()
    return trainr_workout_service.to_out(trainr_workout_repo.get_workout(db, workout_id))


@router.put("/workouts/{workout_id}/completed", response_model=TrainrWorkoutOut)
def set_workout_completed(workout_id: int, payload: TrainrWorkoutCompletedIn, db: Session = Depends(get_db)):
    """The planner's one-tap tick, without resending the whole workout."""
    workout = trainr_workout_repo.get_workout(db, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    trainr_workout_repo.set_completed(db, workout, payload.is_completed)
    db.commit()
    return trainr_workout_service.to_out(trainr_workout_repo.get_workout(db, workout_id))


@router.delete("/workouts/{workout_id}", status_code=204)
def delete_workout(workout_id: int, db: Session = Depends(get_db)):
    workout = trainr_workout_repo.get_workout(db, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    trainr_workout_repo.delete_workout(db, workout)
    db.commit()
