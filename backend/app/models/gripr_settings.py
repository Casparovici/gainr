from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Only one row ever exists (id is always this constant) — same singleton pattern as
# portfolio_settings, kept as a separate table since it's scoped to gripr, not gainr.
SETTINGS_ID = 1


class GriprSettings(Base):
    __tablename__ = "pefi_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=SETTINGS_ID)
    # 1-28: every month has a 28th, so this never needs end-of-month fallback logic, and it
    # keeps naive "+1 month" day-preserving arithmetic (Python's relativedelta, JS's
    # Date.setMonth) safe on both sides of the stack. Default 1 = today's plain calendar month.
    period_start_day: Mapped[int] = mapped_column(Integer, default=1)
