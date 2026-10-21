import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TrainrMuscleGroup(str, enum.Enum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    ARMS = "arms"
    LEGS = "legs"
    CORE = "core"
    FULL_BODY = "full_body"


class TrainrEquipment(str, enum.Enum):
    DUMBBELL = "dumbbell"
    BARBELL = "barbell"
    PULL_UP_BAR = "pull_up_bar"
    BODYWEIGHT = "bodyweight"
    OTHER = "other"


class TrainrExercise(Base):
    """One gym exercise in the user's catalogue ("Dumbbell press"). An open, user-extensible list
    -- the GriprCategory/ListrItem shape, not a closed enum -- seeded with home-gym suggestions by
    the migration that created it (docs/adr/0037). Archiving hides an exercise from the picker
    without touching the workouts that already used it. `demo_id` links a how-to demo from the
vendored free-exercise-db catalogue (ADR 0040); unlinked is fine."""

    __tablename__ = "trainr_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    muscle_group: Mapped[TrainrMuscleGroup] = mapped_column(Enum(TrainrMuscleGroup))
    equipment: Mapped[TrainrEquipment] = mapped_column(Enum(TrainrEquipment))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    demo_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
