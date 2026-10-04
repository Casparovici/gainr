import enum
from datetime import date as date_, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.garden_zone import GardenZoneShape

PERCENT = Numeric(5, 2)
# A plant marker defaults small and round -- roughly a quarter the size of a freshly-created
# zone -- since a marker is a point on the map, not a bed.
DEFAULT_MARKER_SIZE = Decimal("6.00")


class GardenPlantType(str, enum.Enum):
    PLANT = "plant"
    TREE = "tree"
    SHRUB = "shrub"
    OTHER = "other"


# The lucide-react icon a marker renders, picked independently of `type` -- a user might want a
# "tree" icon on something they've catalogued as a shrub. Kept as a small fixed set (matching
# `GardenActionType`'s closed-list-plus-fallback shape) rather than an open string, so the
# frontend never has to render an icon name it doesn't recognize.
class GardenPlantStatus(str, enum.Enum):
    THRIVING = "thriving"
    STRUGGLING = "struggling"
    DEAD = "dead"


class GardenPlantIcon(str, enum.Enum):
    SPROUT = "sprout"
    TREE_DECIDUOUS = "tree_deciduous"
    TREE_PINE = "tree_pine"
    TREES = "trees"
    LEAF = "leaf"
    LEAFY_GREEN = "leafy_green"
    FLOWER = "flower"
    FLOWER2 = "flower2"


class GardenPlant(Base):
    """A single plant or tree in the catalog. `x`/`y` are its marker's percent-of-canvas position
    on its area's map -- nullable, since a plant can be catalogued (and cared for) before it's
    ever placed on the map. `marker_*` control how the marker itself renders, independent of the
    plant's `type` -- a marker's shape/size/icon are display choices, not taxonomy."""

    __tablename__ = "garden_plants"

    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("garden_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    species: Mapped[str | None] = mapped_column(String(200), nullable=True)
    type: Mapped[GardenPlantType] = mapped_column(Enum(GardenPlantType))
    planted_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    x: Mapped[Decimal | None] = mapped_column(PERCENT, nullable=True)
    y: Mapped[Decimal | None] = mapped_column(PERCENT, nullable=True)
    marker_shape: Mapped[GardenZoneShape] = mapped_column(Enum(GardenZoneShape), default=GardenZoneShape.CIRCLE)
    marker_width: Mapped[Decimal] = mapped_column(PERCENT, default=DEFAULT_MARKER_SIZE)
    marker_height: Mapped[Decimal] = mapped_column(PERCENT, default=DEFAULT_MARKER_SIZE)
    icon: Mapped[GardenPlantIcon | None] = mapped_column(Enum(GardenPlantIcon), nullable=True)
    # Unlike listr's inventory_status (nullable, opt-in tracking per catalog item -- most
    # products aren't stocked at all), every catalogued plant already implicitly has a status --
    # it's alive and fine until you say otherwise -- so this defaults to THRIVING rather than
    # being nullable. A manual flag, not inferred from care-log history.
    status: Mapped[GardenPlantStatus] = mapped_column(Enum(GardenPlantStatus), default=GardenPlantStatus.THRIVING)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    area = relationship("GardenArea", back_populates="plants")
    care_logs = relationship(
        "GardenCareLog", back_populates="plant", cascade="all, delete-orphan", order_by="GardenCareLog.performed_on.desc()"
    )
    care_schedules = relationship("GardenCareSchedule", back_populates="plant", cascade="all, delete-orphan")
