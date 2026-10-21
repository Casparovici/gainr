from datetime import date as date_
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.trainr_exercise import TrainrEquipment, TrainrMuscleGroup
from app.models.trainr_workout import TrainrActivityType

# -- exercises ------------------------------------------------------------------------------


class TrainrExerciseDemoOut(BaseModel):
    """A how-to demo (ADR 0040): a start and an end photo to flip between, and the steps."""

    id: str
    name: str
    equipment: str | None
    image_urls: list[str]
    instructions: list[str]


class TrainrExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    muscle_group: TrainrMuscleGroup
    equipment: TrainrEquipment
    is_archived: bool
    demo_id: str | None = None
    # The linked demo, resolved from the catalogue; None when unlinked or no longer in it.
    demo: TrainrExerciseDemoOut | None = None
    # From completed workouts only, computed by trainr_workout_service.exercise_stats -- what the
    # workout form shows as "vorige keer" so the next session can build on the last one.
    times_performed: int = 0
    last_performed_on: date_ | None = None
    last_sets: int | None = None
    last_reps: int | None = None
    last_weight_kg: Decimal | None = None
    best_weight_kg: Decimal | None = None


class TrainrExerciseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    muscle_group: TrainrMuscleGroup
    equipment: TrainrEquipment = TrainrEquipment.DUMBBELL
    demo_id: str | None = Field(default=None, max_length=120)


class TrainrExerciseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    muscle_group: TrainrMuscleGroup | None = None
    equipment: TrainrEquipment | None = None
    is_archived: bool | None = None
    # Sent as null, unlinks the demo.
    demo_id: str | None = Field(default=None, max_length=120)


# -- workouts -------------------------------------------------------------------------------


class TrainrWorkoutEntryIn(BaseModel):
    exercise_id: int
    sets: int | None = Field(default=None, ge=1, le=100)
    reps: int | None = Field(default=None, ge=1, le=1000)
    weight_kg: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=2)
    duration_seconds: int | None = Field(default=None, ge=1, le=24 * 3600)
    notes: str | None = Field(default=None, max_length=200)


class TrainrWorkoutEntryOut(BaseModel):
    id: int
    exercise_id: int
    exercise_name: str
    muscle_group: TrainrMuscleGroup
    sets: int | None
    reps: int | None
    weight_kg: Decimal | None
    duration_seconds: int | None
    notes: str | None


class TrainrWorkoutIn(BaseModel):
    """The whole workout, entries included -- create and update both send the full state, the
    way the weekplanner's day PUT does, so the form never has to diff its exercise list."""

    activity_type: TrainrActivityType
    date: date_
    is_completed: bool = False
    duration_seconds: int | None = Field(default=None, ge=1, le=48 * 3600)
    distance_km: Decimal | None = Field(default=None, gt=0, le=10000, decimal_places=2)
    max_speed_kmh: Decimal | None = Field(default=None, gt=0, le=200, decimal_places=1)
    # Football and padel only (trainr_workout_service.validate).
    calories_kcal: int | None = Field(default=None, ge=1, le=20000)
    avg_heart_rate_bpm: int | None = Field(default=None, ge=30, le=250)
    max_heart_rate_bpm: int | None = Field(default=None, ge=30, le=250)
    notes: str | None = Field(default=None, max_length=2000)
    entries: list[TrainrWorkoutEntryIn] = Field(default_factory=list, max_length=100)


class TrainrWorkoutCompletedIn(BaseModel):
    is_completed: bool


class TrainrWorkoutOut(BaseModel):
    id: int
    activity_type: TrainrActivityType
    date: date_
    is_completed: bool
    duration_seconds: int | None
    distance_km: Decimal | None
    max_speed_kmh: Decimal | None
    calories_kcal: int | None
    avg_heart_rate_bpm: int | None
    max_heart_rate_bpm: int | None
    notes: str | None
    entries: list[TrainrWorkoutEntryOut]
    # Derived from distance and time on every read, never stored.
    avg_speed_kmh: Decimal | None
    pace_seconds_per_km: int | None
    # Home gym: sum of sets x reps x weight over the entries that carry all three.
    volume_kg: Decimal | None


# -- history summary --------------------------------------------------------------------------


class TrainrActivitySummary(BaseModel):
    activity_type: TrainrActivityType
    workouts: int
    total_duration_seconds: int
    total_distance_km: Decimal | None
    # Over the workouts that carry both a distance and a time: total distance / total time.
    avg_speed_kmh: Decimal | None
    total_volume_kg: Decimal | None
    total_calories_kcal: int | None = None
    # Football and padel: the sessions' average heart rates weighted by their time, and the peak.
    avg_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None


class TrainrSummaryOut(BaseModel):
    date_from: date_
    date_to: date_
    workouts: int
    total_duration_seconds: int
    by_activity: list[TrainrActivitySummary]


# -- overview ---------------------------------------------------------------------------------
# One activity's dashboard, all computed by trainr_overview_service from its done workouts.


class TrainrPeriodTotals(BaseModel):
    workouts: int
    duration_seconds: int
    distance_km: Decimal | None
    avg_speed_kmh: Decimal | None
    volume_kg: Decimal | None
    calories_kcal: int | None = None
    avg_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None


class TrainrPeriodTile(BaseModel):
    key: str  # "week" | "month" | "year" | "all"
    date_from: date_ | None
    date_to: date_
    current: TrainrPeriodTotals
    # The previous period up to the same point (Mon-Wed last week against Mon-Wed this week), so
    # a period still running isn't compared with a whole one. None for "all".
    previous: TrainrPeriodTotals | None


class TrainrSeriesPoint(BaseModel):
    period_start: date_
    workouts: int
    duration_seconds: int
    distance_km: Decimal | None
    avg_speed_kmh: Decimal | None
    pace_seconds_per_km: int | None
    volume_kg: Decimal | None
    calories_kcal: int | None = None
    avg_heart_rate_bpm: int | None = None


class TrainrRecord(BaseModel):
    # longest_distance | longest_duration | fastest_avg_speed | best_pace | heaviest_lift | biggest_volume
    # | most_calories | highest_heart_rate
    kind: str
    value: Decimal
    workout_id: int
    date: date_
    detail: str | None = None  # the exercise, for heaviest_lift


class TrainrMuscleGroupShare(BaseModel):
    muscle_group: TrainrMuscleGroup
    sets: int
    volume_kg: Decimal | None


class TrainrExerciseProgressPoint(BaseModel):
    date: date_
    max_weight_kg: Decimal | None
    volume_kg: Decimal | None


class TrainrExerciseProgress(BaseModel):
    exercise_id: int
    name: str
    sessions: int
    best_weight_kg: Decimal | None
    points: list[TrainrExerciseProgressPoint]


class TrainrOverviewOut(BaseModel):
    activity_type: TrainrActivityType
    today: date_
    tiles: list[TrainrPeriodTile]
    # The last 12 months including the current one, and every year since the first workout --
    # empty periods included, so a chart's axis has no gaps.
    monthly: list[TrainrSeriesPoint]
    yearly: list[TrainrSeriesPoint]
    records: list[TrainrRecord]
    # Home gym only (empty otherwise).
    muscle_groups: list[TrainrMuscleGroupShare]
    exercises: list[TrainrExerciseProgress]
