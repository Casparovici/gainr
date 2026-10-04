from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.listr_list import QUANTITY
from app.models.listr_recipe_category import listr_recipe_category_links


class ListrRecipe(Base):
    __tablename__ = "grecipe_recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Same markdown subset MarkdownLite.tsx already renders for gainr's position notes --
    # **bold**/*italic*/lists/headings -- reused as-is for recipe steps.
    instructions: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    # Set on a recipe imported from Mealie (see listr_mealie_service): Mealie's own recipe id,
    # so a re-import updates this row instead of adding a duplicate, and Mealie's last-changed
    # stamp as it sent it, compared as an opaque string to tell "changed since" from "unchanged".
    # NULL for every recipe written in listr itself.
    # unique+index gives create_all the same named unique index the migration creates.
    mealie_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    mealie_updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ingredients = relationship(
        "ListrRecipeIngredient", back_populates="recipe", cascade="all, delete-orphan",
        order_by="ListrRecipeIngredient.sort_order",
    )
    categories = relationship(
        "ListrRecipeCategory", secondary=listr_recipe_category_links, back_populates="recipes",
        order_by="ListrRecipeCategory.sort_order",
    )


class ListrRecipeIngredient(Base):
    __tablename__ = "grecipe_recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("grecipe_recipes.id"), index=True)
    grocery_item_id: Mapped[int] = mapped_column(ForeignKey("grecipe_items.id"))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, default=1)
    unit: Mapped[str] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    recipe = relationship("ListrRecipe", back_populates="ingredients")
    grocery_item = relationship("ListrItem")
