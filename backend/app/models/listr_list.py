from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

QUANTITY = Numeric(10, 3)


class ListrList(Base):
    """A saved, reusable shopping list ("Weekboodschappen", "BBQ") -- not one perpetual cart.
    Archived rather than deleted so an old list can be revisited or duplicated later."""

    __tablename__ = "grecipe_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship("ListrListItem", back_populates="list", cascade="all, delete-orphan")


class ListrListItem(Base):
    """One line on a list. No is_archived -- a checked-off, cleared line has no lasting record
    value (unlike a gripr transaction), so clearing checked items hard-deletes these rows."""

    __tablename__ = "grecipe_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grecipe_lists.id"), index=True)
    grocery_item_id: Mapped[int] = mapped_column(ForeignKey("grecipe_items.id"))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, default=1)
    # Defaults from ListrItem.default_unit at add-time but is its own column -- editable per
    # line, and merge logic (see listr_list_service) only combines lines whose unit matches.
    unit: Mapped[str] = mapped_column(String(32))
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    list = relationship("ListrList", back_populates="items")
    grocery_item = relationship("ListrItem")
