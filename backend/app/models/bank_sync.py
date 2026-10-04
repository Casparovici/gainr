from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BankConnection(Base):
    """One bank read through Enable Banking (ING, Trade Republic) or its own API (Trading 212),
    and whether it books anything. Rows are seeded by migration, one per supported bank; nothing in the app creates
    them. `session_id` names the Enable Banking session behind the reader's consent at that bank
    -- useless without the app's private key, which lives outside the database. `pending_state`
    is the one-time value a consent in progress was started with; the callback must bring exactly
    that back, which is also how it knows which bank it's for. Only transactions dated on or after
    `since` are ever booked, so switching a bank on never rewrites older, hand-entered history.
    `source_prefix` starts every reference this bank's entries get ("ing:…", "tr:…"), keeping
    them apart in gripr's `source_ref`. See docs/adr/0029-ing-transactions-into-gripr.md."""

    __tablename__ = "bank_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    aspsp_name: Mapped[str] = mapped_column(String(80))
    aspsp_country: Mapped[str] = mapped_column(String(2))
    source_prefix: Mapped[str] = mapped_column(String(8), unique=True)
    # How it's read: "enablebanking" (a PSD2 consent the reader renews) or "trading212" (Trading
    # 212's own API, with a key from the server's environment -- no consent, so session_id and
    # valid_until stay empty). See docs/adr/0031-trading212-sync.md.
    provider: Mapped[str] = mapped_column(String(16), default="enablebanking", server_default="enablebanking")
    # The bank sends only date, amount and direction -- no counterparty, description or reference
    # (Trade Republic through Enable Banking). Its entries can't be categorised from, so the sync
    # only checks them against what's already in gripr and books the rest; see bank_sync_service.
    amount_only: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    since: Mapped[date | None] = mapped_column(Date, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # UTC, naive -- when the bank stops honouring the consent (ING 180 days, Trade Republic 90).
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pending_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # UTC, naive
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class BankSyncAccount(Base):
    """An account a bank consent covers, and the gripr account its transactions land on (none:
    skipped). Keyed on the IBAN, not Enable Banking's account uid, because every new consent hands
    the same account a new uid -- reconnecting must keep the reader's mapping."""

    __tablename__ = "bank_sync_accounts"

    iban: Mapped[str] = mapped_column(String(34), primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("bank_connections.id", ondelete="CASCADE"), index=True)
    # The account's uid in the current session; null when the latest consent didn't include it.
    eb_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product: Mapped[str] = mapped_column(String(60), default="")
    holder_name: Mapped[str] = mapped_column(String(120), default="")
    gripr_account_id: Mapped[int | None] = mapped_column(ForeignKey("pefi_accounts.id", ondelete="SET NULL"), nullable=True)


class BankCounterpartyRule(Base):
    """"Money to or from this counterparty is a transfer with that gripr account" -- for the
    reader's own accounts the sync can't see by IBAN (an ING savings account the API doesn't
    expose, recognised by its number in the description; a broker paid through a payment
    processor; a savings plan at a bank that sends amounts only). Matches when every set field
    matches: the counterparty IBAN exactly; `text_contains` somewhere in the counterparty name or
    description (case-, space- and punctuation-insensitive); exactly `amount`, or at most
    `amount_max` (a saveback that varies but never exceeds €15); with `day_of_month`, a date
    within a few days of that day; with `direction`, only money going "out" or coming "in". At
    least one of IBAN, text, amount and amount_max is set. Accounts synced from any connected bank
    need no rule; they're recognised by IBAN already. Applies to every bank."""

    __tablename__ = "bank_counterparty_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    text_contains: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str | None] = mapped_column(String(3), nullable=True)  # "out" | "in" | None: either
    gripr_account_id: Mapped[int] = mapped_column(ForeignKey("pefi_accounts.id", ondelete="CASCADE"))


class BankSyncedTransaction(Base):
    """A bank entry that has been handled -- the record that makes handling happen exactly once,
    and says how: booked as a new gripr row, matched to a row that was already there (entered by
    hand), booked as the occurrence of a recurring rule it fulfils, or skipped as the incoming half
    of a transfer between two synced accounts (the outgoing half books it). `reference` is the
    bank's own entry reference behind its connection's prefix -- the same string the booked gripr
    row carries as `source_ref`."""

    __tablename__ = "bank_synced_transactions"

    reference: Mapped[str] = mapped_column(String(80), primary_key=True)
    iban: Mapped[str] = mapped_column(String(34))
    transacted_on: Mapped[date] = mapped_column(Date, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    outcome: Mapped[str] = mapped_column(String(16))
    gripr_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_transactions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recurring_id: Mapped[int | None] = mapped_column(
        ForeignKey("pefi_recurring_transactions.id", ondelete="SET NULL"), nullable=True
    )
    # The merchant a card payment was made at (Trading 212 names it; ING and Trade Republic
    # entries leave this empty), normalised -- how a new payment at the same merchant finds the
    # category the reader gave the last one.
    merchant: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
