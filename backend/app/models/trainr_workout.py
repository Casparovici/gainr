import enum
from datetime import date as date_, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TrainrActivityType(str, enum.Enum):
    """A closed list (the GardenActionType shape): each type decides which fields a workout
    carries -- see trainr_workout_service.DISTANCE_ACTIVITIES / SET_ACTIVITIES / MATCH_ACTIVITIES."""

    HOME_GYM = "home_gym"
    RUNNING = "running"
    CYCLING = "cycling"
    FOOTBALL = "football"
    PADEL = "padel"


class TrainrWorkout(Base):
    """One session on one date -- planned or done. A planned workout is the same row with
    `is_completed` false, so ticking it off in the planner is what moves it into the history
    (the weekplanner's `is_cooked` step, docs/adr/0006). Several per day are allowed.

    Running/cycling use `distance_km`, `duration_seconds` and `max_speed_kmh`; average speed
    and pace are derived from distance and time on read, never stored. Home gym uses `entries`
    (and optionally `duration_seconds` for the whole session). Football and padel use
    `duration_seconds` plus the three body figures a watch reports: calories and average and
    maximum heart rate (docs/adr/0037)."""

    __tablename__ = "trainr_workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_type: Mapped[TrainrActivityType] = mapped_column(Enum(TrainrActivityType))
    date: Mapped[date_] = mapped_column(Date, index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    max_speed_kmh: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    calories_kcal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Where an imported workout came from ("strava:<activity id>"), so re-running an import
    # matches what's already there instead of adding it twice. None for a workout entered here.
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    entries: Mapped[list["TrainrWorkoutEntry"]] = relationship(
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="TrainrWorkoutEntry.sort_order",
    )


class TrainrWorkoutEntry(Base):
    """One exercise within a home-gym session: "3 x 10 at 12 kg". Sets that differ in weight are
    simply two entries for the same exercise -- one row per exercise keeps logging to a single
    line, which is what makes manual entry quick (docs/adr/0037). `duration_seconds` is for timed
    holds (plank) instead of reps."""

    __tablename__ = "trainr_workout_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("trainr_workouts.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("trainr_exercises.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(200), nullable=True)

    workout: Mapped[TrainrWorkout] = relationship(back_populates="entries")
    exercise = relationship("TrainrExercise")
