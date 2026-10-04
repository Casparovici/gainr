"""What's worth telling the reader when they come back to gripr: what the syncs booked, money that
came back for something they fronted (or still hasn't, a month on), and bank connections that need
them. Worked out from what's already stored, nothing kept of its own; the frontend remembers per
device when the reader last looked and passes it as `since`.

Each item carries `at`, the moment it became news, so the frontend can tell new from already seen.
Items about the syncs and repayments only cover what happened after `since`; the reminders (money
still owed, a bank needing attention) stay listed for as long as they're true.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.repositories import bank_sync_repo
from app.services import bank_sync_service, gripr_receivable_service
from app.services.picnic_sync_service import SOURCE_REF_PREFIX as PICNIC_PREFIX

# Money fronted and still not back after this long gets a reminder.
OWED_REMINDER_DAYS = 30
# A consent ending within this many days is worth a reconnect now (the bank settings warn the same).
CONSENT_WARNING_DAYS = 14

T = GriprTransactionType


@dataclass(frozen=True)
class Notification:
    key: str  # stable per item, so the frontend can tell items apart
    kind: str  # "synced" | "money_back" | "still_owed" | "bank"
    at: datetime  # UTC: when this became news
    title: str
    detail: str | None
    link: str


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def _eur(amount: Decimal) -> str:
    return f"€ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _what(expense: GriprTransaction) -> str:
    return expense.notes or (expense.category.name if expense.category else "an expense")


def _sources(db: Session) -> dict[str, str]:
    """source_ref prefix -> what to call it: each bank by name, and Picnic."""
    names = {f"{c.source_prefix}:": c.aspsp_name for c in bank_sync_repo.list_connections(db)}
    names[PICNIC_PREFIX] = "Picnic"
    return names


def _synced(db: Session, since: datetime) -> list[Notification]:
    """One item per source: how many transactions it booked since `since`, and how many of those
    still need a category."""
    since_naive = since.astimezone(timezone.utc).replace(tzinfo=None)
    rows = db.execute(
        select(GriprTransaction).where(GriprTransaction.created_at > since_naive, GriprTransaction.source_ref.is_not(None))
    ).scalars().all()
    sources = _sources(db)
    grouped: dict[str, list[GriprTransaction]] = {}
    for row in rows:
        name = next((n for prefix, n in sources.items() if row.source_ref.startswith(prefix)), None)
        if name is not None:
            grouped.setdefault(name, []).append(row)
    items = []
    for name, booked in sorted(grouped.items()):
        uncategorised = sum(1 for t in booked if t.type != T.TRANSFER and t.category_id is None)
        count = len(booked)
        items.append(Notification(
            key=f"synced:{name}",
            kind="synced",
            at=_utc(max(t.created_at for t in booked)),
            title=f"{count} new {'transaction' if count == 1 else 'transactions'} from {name}",
            detail=f"{uncategorised} {'needs' if uncategorised == 1 else 'need'} a category" if uncategorised else None,
            link="/gripr/transactions?category=uncategorized" if uncategorised else "/gripr/transactions",
        ))
    return items


def _money_back(db: Session, since: datetime) -> list[Notification]:
    """Repayments since `since` for expenses the reader fronted."""
    since_naive = since.astimezone(timezone.utc).replace(tzinfo=None)
    refunds = db.execute(
        select(GriprTransaction).where(
            GriprTransaction.type == T.REFUND,
            GriprTransaction.refund_of_id.is_not(None),
            GriprTransaction.created_at > since_naive,
        )
    ).scalars().all()
    items = []
    for refund in refunds:
        expense = refund.refund_of
        if expense is None or expense.expected_back is None:
            continue
        who = f" from {expense.expected_from}" if expense.expected_from else ""
        items.append(Notification(
            key=f"money_back:{refund.id}",
            kind="money_back",
            at=_utc(refund.created_at),
            title=f"{_eur(refund.amount)} came back{who}",
            detail=f"for {_what(expense)}",
            link="/gripr",
        ))
    return items


def _still_owed(db: Session, today: date) -> list[Notification]:
    items = []
    for r in gripr_receivable_service.list_open(db):
        reminder_day = r.expense.date + timedelta(days=OWED_REMINDER_DAYS)
        if reminder_day > today:
            continue
        who = f" by {r.expense.expected_from}" if r.expense.expected_from else ""
        items.append(Notification(
            key=f"still_owed:{r.expense.id}",
            kind="still_owed",
            at=datetime.combine(reminder_day, time.min, timezone.utc),
            title=f"{_eur(r.outstanding)} still owed{who}",
            detail=f"for {_what(r.expense)}, since {r.expense.date:%d %b %Y}",
            link="/gripr",
        ))
    return items


def _banks(db: Session, now: datetime) -> list[Notification]:
    """Banks that need the reader: a consent that's ended or about to, or reads that are failing.
    Dated by the last successful sync, which stays put while the problem lasts -- so a problem
    already seen doesn't light the dot again on every visit."""
    items = []
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    for c in bank_sync_repo.list_connections(db):
        if not c.enabled:
            continue
        last_ok = _utc(c.last_synced_at) if c.last_synced_at else epoch
        if c.provider != bank_sync_service.TRADING212 and not bank_sync_service.is_connected(c):
            items.append(Notification(
                key=f"bank:{c.source_prefix}:reconnect", kind="bank", at=last_ok,
                title=f"Reconnect {c.aspsp_name}", detail="Its consent has ended, so nothing syncs from it.", link="/gripr",
            ))
            continue
        if c.valid_until is not None:
            warn_from = _utc(c.valid_until) - timedelta(days=CONSENT_WARNING_DAYS)
            if now >= warn_from:
                items.append(Notification(
                    key=f"bank:{c.source_prefix}:expiring", kind="bank", at=warn_from,
                    title=f"{c.aspsp_name} needs a reconnect soon",
                    detail=f"Its consent ends on {_utc(c.valid_until):%d %b}.", link="/gripr",
                ))
        if c.last_error:
            items.append(Notification(
                key=f"bank:{c.source_prefix}:error", kind="bank", at=last_ok,
                title=f"{c.aspsp_name} isn't syncing", detail=c.last_error, link="/gripr",
            ))
    return items


def list_notifications(db: Session, since: datetime, now: datetime | None = None) -> list[Notification]:
    """Everything worth mentioning, newest first."""
    now = now or datetime.now(timezone.utc)
    items = _synced(db, since) + _money_back(db, since) + _still_owed(db, now.date()) + _banks(db, now)
    return sorted(items, key=lambda n: n.at, reverse=True)
