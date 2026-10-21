from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ListrStore(Base):
    """A supermarket the user shops at. What makes it a store is the order its aisles come in: a
    list set to this store shows its categories in this order, so the list follows the walk through
    the shop (docs/adr/0052-listr-store-order.md)."""

    __tablename__ = "grecipe_stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    category_positions = relationship(
        "ListrStoreCategory", cascade="all, delete-orphan", order_by="ListrStoreCategory.position"
    )


class ListrStoreCategory(Base):
    """Where one category comes in a store's walk (lower first). A category the store has no row
    for comes after those that have one, in the global category order."""

    __tablename__ = "grecipe_store_categories"

    store_id: Mapped[int] = mapped_column(ForeignKey("grecipe_stores.id"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("grecipe_categories.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
