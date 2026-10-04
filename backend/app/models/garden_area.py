from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GardenArea(Base):
    """One garden map — e.g. "Front yard", "Back yard". Each area owns its own canvas of zones
    and plant markers, since a household can easily have more than one distinct plot."""

    __tablename__ = "garden_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    zones = relationship("GardenZone", back_populates="area", cascade="all, delete-orphan")
    plants = relationship("GardenPlant", back_populates="area", cascade="all, delete-orphan")
