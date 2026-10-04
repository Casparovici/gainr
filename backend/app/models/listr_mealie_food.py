from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ListrMealieFood(Base):
    """Which catalog product a Mealie "food" means -- chosen once by the reader during a Mealie
    import (Mealie's "ei" is listr's "Eieren") and reused for every later recipe using it. The
    same "confirm once, remembered" idea as ListrItem.picnic_product_id, but as its own table
    because several Mealie foods can mean the same product ("ei", "eieren", "eidooier"...).

    Foods whose name already equals a catalog product's name match without a row here. See
    docs/adr/0022-listr-mealie-import.md.
    """

    __tablename__ = "grecipe_mealie_foods"

    mealie_food_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Display cache of what Mealie called it when mapped; Mealie is never re-queried to render it.
    mealie_food_name: Mapped[str] = mapped_column(String(200))
    grocery_item_id: Mapped[int] = mapped_column(ForeignKey("grecipe_items.id"))

    grocery_item = relationship("ListrItem")
