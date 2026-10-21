from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BrokerConnection(Base):
    """A broker whose own records book into one gainr portfolio: fills, dividends, and (for
    Trading 212) a weekly deposit of the interest and cashback paid on its cash. Rows are seeded
    by migration, one per supported broker; `broker` is the name its transactions carry in
    `transactions.broker` ("Trading212"). Nothing dated before `since` is ever booked, so switching
    on never rewrites history the reader entered by hand. `unmapped` holds, as JSON, the
    instruments the last run couldn't book because no asset has their ISIN -- the reader links them
    from the Transactions page. See docs/adr/0031-trading212-sync.md."""

    __tablename__ = "broker_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    broker: Mapped[str] = mapped_column(String(64), unique=True)
    portfolio_id: Mapped[int | None] = mapped_column(ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    since: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # UTC, naive
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    unmapped: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The gripr account Trading 212's spending cashback is booked into, as income. Unset: cashback
    # stays part of the weekly deposit in gainr, as it was before the two were told apart.
    cashback_account_id: Mapped[int | None] = mapped_column(ForeignKey("pefi_accounts.id", ondelete="SET NULL"), nullable=True)


class BrokerSyncedItem(Base):
    """A broker record that has been handled, and how: booked as a new gainr transaction, or
    matched to one the reader had already entered. `reference` is "<prefix>:<kind>:<id>"
    ("t212:fill:58259128094", "t212:dividend:…", "t212:week:2026-W40") -- the same string a booked
    transaction carries as `source_ref`, so each record is handled exactly once."""

    __tablename__ = "broker_synced_items"

    reference: Mapped[str] = mapped_column(String(80), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(16))
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
