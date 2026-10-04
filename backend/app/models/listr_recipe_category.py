from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# A recipe can carry several tags at once (e.g. "Italiaans" + "Vegetarisch"), unlike the
# product catalog's ListrCategory which is a required one-per-item container -- so this is a
# separate table/association rather than reusing that one (see docs/adr/0006).
listr_recipe_category_links = Table(
    "grecipe_recipe_category_links",
    Base.metadata,
    Column("recipe_id", ForeignKey("grecipe_recipes.id"), primary_key=True),
    Column("category_id", ForeignKey("grecipe_recipe_categories.id"), primary_key=True),
)


class ListrRecipeCategory(Base):
    __tablename__ = "grecipe_recipe_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    recipes = relationship("ListrRecipe", secondary=listr_recipe_category_links, back_populates="categories")
