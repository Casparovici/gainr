import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BriefrAttention(str, enum.Enum):
    """How much a report asks of the reader: something to act on, to keep an eye on, or just to
    know. A report is never calmer than its most urgent item (briefr_report_service)."""

    ACT = "act"
    WATCH = "watch"
    INFO = "info"


class BriefrVerdict(str, enum.Enum):
    """An agent's call on one finding -- for the holdings scan, one position."""

    ACT = "act"
    WATCH = "watch"
    IGNORE = "ignore"


class BriefrReport(Base):
    """One agent run's report, imported from a Markdown file the agent committed to the agents
    repository (docs/adr/0044-briefr-agent-reports.md). Agents never write to the app: the file is
    the source and `source_path` (relative to the repository, e.g.
    "reports/holdings-scan/2026-10-19.md") identifies it, so re-importing is idempotent and a file
    the agent rewrote replaces its report. `content_hash` lets an import skip files that haven't
    changed. Reading and archiving are the reader's own state, kept here, not in the file."""

    __tablename__ = "briefr_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_path: Mapped[str] = mapped_column(String(300), unique=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(64), index=True)
    # UTC, naive like every other timestamp in the database.
    run_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    attention: Mapped[BriefrAttention] = mapped_column(Enum(BriefrAttention))
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship(
        "BriefrReportItem", back_populates="report", order_by="BriefrReportItem.sort_order",
        cascade="all, delete-orphan",
    )


class BriefrReportItem(Base):
    """One finding in a report, with the agent's verdict on it. `symbol` is what the agent wrote
    (a ticker or Yahoo symbol from the context it was given); `asset_id` is the gainr asset it
    resolved to on import, so a position can list what agents said about it. Both are empty for a
    finding that isn't about a holding (an app-builder run's pull request, a market-wide note)."""

    __tablename__ = "briefr_report_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("briefr_reports.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    verdict: Mapped[BriefrVerdict] = mapped_column(Enum(BriefrVerdict))
    headline: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A JSON list of http(s) URLs the finding rests on, like Asset.news_sources' JSON-in-Text.
    sources: Mapped[str] = mapped_column(Text, default="[]")
    # A suggested recipe (schemas.briefr.ReportFileRecipe as JSON), for an agent like the home
    # chef whose findings can be planned in listr (docs/adr/0054). NULL for every other finding.
    recipe: Mapped[str | None] = mapped_column(Text, nullable=True)

    report = relationship("BriefrReport", back_populates="items")
    asset = relationship("Asset")
