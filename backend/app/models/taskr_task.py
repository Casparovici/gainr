from datetime import date as date_, datetime

from sqlalchemy import Date, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TaskrTask(Base):
    """A to-do the user adds in taskr itself ("bel de loodgieter"), the one kind of agenda item
    taskr owns rather than reads from another module (the addendum on docs/adr/0038). Every task
    has a day; ticking it off stamps `completed_at` instead of deleting it, so a mis-tap can be
    undone."""

    __tablename__ = "taskr_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date_] = mapped_column(Date, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
