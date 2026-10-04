from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GriprBankLogo(Base):
    """Locally cached brand icon for one entry in gripr_bank_logo_service.GRIPR_BANKS.

    Same reasoning as AssetLogo: fetched once from the bank's own site and stored here, never
    pointed at from a third-party CDN and never re-fetched once a copy exists. Keyed by the
    fixed catalog key (not an id/FK) since the catalog itself is a small hand-picked dict in
    code, not a database table of its own.
    """

    __tablename__ = "pefi_bank_logos"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(64))
    image: Mapped[bytes] = mapped_column(LargeBinary)
    source_url: Mapped[str] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
