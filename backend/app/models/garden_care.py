import enum
from datetime import date as date_, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GardenActionType(str, enum.Enum):
    WATER = "water"
    PRUNE = "prune"
    TRIM = "trim"
    FERTILIZE = "fertilize"
    HARVEST = "harvest"
    PEST_CONTROL = "pest_control"
    OTHER = "other"


class GardenScheduleFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class GardenCareLog(Base):
    """A journal entry -- "I did this, on this date" -- for one plant. `custom_label` only means
    anything when `action_type` is OTHER, the same way a schedule's does."""

    __tablename__ = "garden_care_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("garden_plants.id"), index=True)
    action_type: Mapped[GardenActionType] = mapped_column(Enum(GardenActionType))
    custom_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    performed_on: Mapped[date_] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A growth-journal photo, stored inline rather than on disk so it's automatically covered by
    # the existing whole-database backup/restore story (docs/adr/0013) instead of needing its own
    # backup path. The frontend resizes to a modest max dimension before upload, so this stays
    # small at this app's personal-garden scale.
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plant = relationship("GardenPlant", back_populates="care_logs")

    @property
    def has_photo(self) -> bool:
        return self.photo is not None


class GardenCareSchedule(Base):
    """A repeat rule -- "water this every 3 days" -- mirroring gripr's Recurring rules. There's no
    stored `next_due_date` and nothing auto-books a log entry: due dates are computed on read
    from the plant's own care-log history (see `garden_care_service.next_due`), the same
    derive-don't-store principle positions and cash already follow elsewhere in this app."""

    __tablename__ = "garden_care_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("garden_plants.id"), index=True)
    action_type: Mapped[GardenActionType] = mapped_column(Enum(GardenActionType))
    custom_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interval_value: Mapped[int] = mapped_column(Integer, default=1)
    frequency: Mapped[GardenScheduleFrequency] = mapped_column(Enum(GardenScheduleFrequency))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # The first occurrence, when the user picked one; None keeps the "creation date plus one
    # interval" fallback for a schedule that was never logged.
    start_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plant = relationship("GardenPlant", back_populates="care_schedules")
