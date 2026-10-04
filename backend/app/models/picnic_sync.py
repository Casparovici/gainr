from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PicnicSyncSettings(Base):
    """Whether -- and where -- a completed Picnic delivery is processed automatically: its
    orders booked as gripr expenses on `gripr_account_id` under `gripr_category_id`, and its
    products added to listr's Voorraad. A single row (id is always 1), like PicnicSession. Off
    until the reader turns it on and picks the account and category; only deliveries on or after
    `since` are ever touched, so switching it on never rewrites older history. See
    docs/adr/0027-picnic-deliveries-into-gripr-and-voorraad.md."""

    __tablename__ = "picnic_sync_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    gripr_account_id: Mapped[int | None] = mapped_column(ForeignKey("pefi_accounts.id", ondelete="SET NULL"), nullable=True)
    gripr_category_id: Mapped[int | None] = mapped_column(ForeignKey("pefi_categories.id", ondelete="SET NULL"), nullable=True)
    since: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PicnicSyncedDelivery(Base):
    """A Picnic delivery that has been processed -- the record that makes processing happen
    exactly once per delivery, and what the order history shows next to it."""

    __tablename__ = "picnic_synced_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    delivered_on: Mapped[date] = mapped_column(Date)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Orders booked as a new gripr expense / orders that already had a matching expense (booked
    # by hand) and were left alone / units added to Voorraad.
    orders_booked: Mapped[int] = mapped_column(Integer, default=0)
    orders_matched: Mapped[int] = mapped_column(Integer, default=0)
    items_restocked: Mapped[int] = mapped_column(Integer, default=0)
