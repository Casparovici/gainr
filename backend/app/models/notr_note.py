from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.notr_label import notr_note_label_links

# A note can be about things in other modules -- gainr positions, gardnr plants, listr recipes --
# each its own association table, the same many-to-many shape labels use. A note with none of
# them is a plain note. Each link is a real relationship on the other side too (Asset.notr_notes,
# GardenPlant.notr_notes, ListrRecipe.notr_notes), so deleting a plant or recipe clears its links.
notr_note_assets = Table(
    "notr_note_assets",
    Base.metadata,
    Column("note_id", ForeignKey("notr_notes.id"), primary_key=True),
    Column("asset_id", ForeignKey("assets.id"), primary_key=True, index=True),
)
notr_note_plants = Table(
    "notr_note_plants",
    Base.metadata,
    Column("note_id", ForeignKey("notr_notes.id"), primary_key=True),
    Column("plant_id", ForeignKey("garden_plants.id"), primary_key=True, index=True),
)
notr_note_recipes = Table(
    "notr_note_recipes",
    Base.metadata,
    Column("note_id", ForeignKey("notr_notes.id"), primary_key=True),
    Column("recipe_id", ForeignKey("grecipe_recipes.id"), primary_key=True, index=True),
)


class NotrNote(Base):
    """A note: a title and a Markdown body, with labels, and optionally linked to positions,
    plants and recipes. Pictures are in the body as `![](/api/notr/images/<id>)`.

    One table, several views: notr lists every note, gainr's Journal lists those linked to a
    position, and a position's, plant's or recipe's own Notes section lists those linked to it --
    the same rows, so nothing is kept in sync (docs/adr/0050-notr-notes.md, extending 0016/0024)."""

    __tablename__ = "notr_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    assets = relationship("Asset", secondary=notr_note_assets, back_populates="notr_notes", order_by="Asset.ticker")
    plants = relationship("GardenPlant", secondary=notr_note_plants, back_populates="notr_notes", order_by="GardenPlant.name")
    recipes = relationship("ListrRecipe", secondary=notr_note_recipes, back_populates="notr_notes", order_by="ListrRecipe.title")
    labels = relationship(
        "NotrLabel", secondary=notr_note_label_links, back_populates="notes", order_by="NotrLabel.sort_order",
    )
