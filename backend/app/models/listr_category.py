from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ListrCategory(Base):
    __tablename__ = "grecipe_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    # User-controlled display order (lower first) -- same drag-to-reorder pattern as
    # GriprCategory/GriprAccount.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Null = derive a colour from the categorical palette by alphabetical rank (the same
    # long-standing default gripr categories/accounts use). Set = the user overrode it.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    items = relationship("ListrItem", back_populates="category")
