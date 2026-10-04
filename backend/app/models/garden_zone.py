import enum
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Percent-of-canvas coordinates (0-100), not pixels -- keeps a zone's position resolution
# independent of whatever size the map renders at.
PERCENT = Numeric(5, 2)


class GardenZoneShape(str, enum.Enum):
    RECT = "rect"
    CIRCLE = "circle"


class GardenZone(Base):
    """A background shape on a garden map -- a lawn, a bed, a path. Purely decorative/labelling;
    plant markers aren't tied to a zone by reference, they just visually sit on top of one."""

    __tablename__ = "garden_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("garden_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    shape: Mapped[GardenZoneShape] = mapped_column(Enum(GardenZoneShape))
    x: Mapped[Decimal] = mapped_column(PERCENT)
    y: Mapped[Decimal] = mapped_column(PERCENT)
    # Rect: width/height of the box. Circle: both hold the diameter (height kept for a uniform
    # read even though a circle only needs one dimension).
    width: Mapped[Decimal] = mapped_column(PERCENT)
    height: Mapped[Decimal] = mapped_column(PERCENT)
    color: Mapped[str] = mapped_column(String(7))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    area = relationship("GardenArea", back_populates="zones")
