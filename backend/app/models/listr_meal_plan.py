from datetime import date as date_, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ListrMealPlan(Base):
    """One row per calendar date -- the "one recipe per day" decision. `recipe_id` is nullable
    so a day can carry just a note ("uit eten", "restjes") with no catalog recipe attached.
    `is_cooked` is a deliberate, explicit step: planning a recipe onto a date is not itself a
    record of having eaten it, so the popularity ranking only counts rows where this is true
    (see docs/adr/0006)."""

    __tablename__ = "grecipe_meal_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date_] = mapped_column(Date, unique=True, index=True)
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("grecipe_recipes.id"), nullable=True)
    # A leftover eaten this day instead of a recipe cooked. Marking the day cooked takes one meal
    # off it (listr_leftover_service.sync_meal_plan_consumption); a day carries a recipe or a
    # leftover, never both.
    leftover_id: Mapped[int | None] = mapped_column(
        ForeignKey("grecipe_leftovers.id", ondelete="SET NULL"), nullable=True
    )
    # Whether a meal has been taken off leftover_id for this row, so saving the day twice (or
    # un-cooking it) can't deduct or refund twice.
    leftover_consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cooked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    recipe = relationship("ListrRecipe")
    leftover = relationship("ListrLeftover")
