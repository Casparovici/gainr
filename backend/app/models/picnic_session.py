from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PicnicSession(Base):
    """The Picnic auth key from the last successful login/2FA verification -- a single row
    (id is always 1), since this is a single-user app with one Picnic account. The email and
    password themselves are never stored here; they live only in the environment
    (config.PICNIC_EMAIL/PICNIC_PASSWORD) and are used solely to obtain this key."""

    __tablename__ = "picnic_session"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    auth_key: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
