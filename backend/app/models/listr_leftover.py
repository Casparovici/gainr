from datetime import date as date_, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ListrLeftover(Base):
    """A batch of cooked meals kept for later -- "bolognese, 2 meals for 4 in the freezer". Not a
    ListrItem: Voorraad counts catalog groceries, this is a dated one-off with a use-by date (see
    docs/adr/0036-listr-leftovers.md). `meals` is a bare tally like ListrItem.inventory_count; a
    row at 0 meals stays in the table (a cooked weekplanner day may still point at it) but drops
    out of the list."""

    __tablename__ = "grecipe_leftovers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("grecipe_recipes.id", ondelete="SET NULL"), nullable=True)
    meals: Mapped[int] = mapped_column(Integer, default=1)
    # Informational only ("each meal feeds 4"); nothing scales or converts with it.
    servings_per_meal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "freezer" or "fridge" -- a plain string, same looseness as ListrItem.default_unit.
    location: Mapped[str] = mapped_column(String(16), default="freezer")
    stored_on: Mapped[date_] = mapped_column(Date)
    use_by: Mapped[date_] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
