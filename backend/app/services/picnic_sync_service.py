"""What happens when a Picnic delivery has arrived: its orders become gripr expenses and its
products go into listr's Voorraad -- once per delivery, and only when switched on. See
docs/adr/0027-picnic-deliveries-into-gripr-and-voorraad.md.

The reader already books some Picnic payments by hand, so an order is first matched against an
existing expense (same account, exactly the charged amount, dated around the order) and only
booked when there isn't one -- turning this on must never double-count.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_transaction_repo, listr_item_repo, picnic_session_repo, picnic_sync_repo
from app.services import gripr_transaction_service, listr_inventory_service
from app.services.picnic_provider import PicnicAuthError, PicnicDelivery, PicnicDeliveryDetail, PicnicProvider, picnic_provider

# How far around an order a hand-booked expense still counts as "that order": a few days before
# (booked on the day it was placed) to a week after the delivery (the day the bank debited it).
MATCH_DAYS_BEFORE_ORDER = 3
MATCH_DAYS_AFTER_DELIVERY = 7
SOURCE_REF_PREFIX = "picnic_order:"


class PicnicSyncNotConnected(Exception):
    """No usable Picnic session -- the reader needs to (re)connect first."""


@dataclass
class SyncResult:
    deliveries: int = 0
    orders_booked: int = 0
    orders_matched: int = 0
    items_restocked: int = 0


def _amounts(*cents: int) -> set[Decimal]:
    return {Decimal(c) / 100 for c in cents}


def _book_orders(db: Session, detail: PicnicDeliveryDetail, delivered_on: date, account_id: int, category_id: int) -> tuple[int, int]:
    """Books each order unless it's already in gripr. "Already in gripr" covers how a Picnic
    charge actually gets booked by hand: one expense for the whole delivery or one per order,
    for the charged amount (with deposit) or the groceries alone (without) -- an exact match on
    any of those, on the chosen account, dated from a few days before the first order to a week
    after the delivery. A matched hand-entered expense is claimed (tagged with the order) so no
    other order can match it again."""
    if not detail.orders:
        return 0, 0
    booked = matched = 0
    claimed: set[int] = set()
    window_from = min(o.created_at.date() for o in detail.orders) - timedelta(days=MATCH_DAYS_BEFORE_ORDER)
    window_to = delivered_on + timedelta(days=MATCH_DAYS_AFTER_DELIVERY)

    def claim(txn, source_ref: str) -> None:
        claimed.add(txn.id)
        # An imported row (pefi_csv:...) keeps its own reference.
        if txn.source_ref is None:
            txn.source_ref = source_ref

    pending = [o for o in detail.orders if not gripr_transaction_repo.exists_by_source_ref(db, f"{SOURCE_REF_PREFIX}{o.id}")]
    matched += len(detail.orders) - len(pending)
    if len(pending) > 1:
        whole = gripr_transaction_repo.find_matching_expense(
            db, account_id,
            _amounts(sum(o.charged_cents for o in pending), sum(o.total_cents for o in pending)),
            window_from, window_to, claimed,
        )
        if whole is not None:
            claim(whole, f"{SOURCE_REF_PREFIX}{pending[0].id}")
            return 0, matched + len(pending)

    for order in pending:
        source_ref = f"{SOURCE_REF_PREFIX}{order.id}"
        existing = gripr_transaction_repo.find_matching_expense(
            db, account_id, _amounts(order.charged_cents, order.total_cents), window_from, window_to, claimed
        )
        if existing is not None:
            claim(existing, source_ref)
            matched += 1
            continue
        gripr_transaction_service.create_transaction(
            db,
            date=order.created_at.date(),
            type=GriprTransactionType.EXPENSE,
            amount=Decimal(order.charged_cents) / 100,
            account_id=account_id,
            category_id=category_id,
            notes="Picnic",
            source_ref=source_ref,
        )
        booked += 1
    return booked, matched


def _restock(db: Session, detail: PicnicDeliveryDetail) -> int:
    """Adds each delivered product to the Voorraad tally of every tracked catalog item linked to
    it. Untracked items are left alone -- tracking stays the reader's opt-in."""
    units_by_product: dict[str, int] = {}
    for product_id, quantity in detail.articles:
        units_by_product[product_id] = units_by_product.get(product_id, 0) + quantity
    restocked = 0
    for item in listr_item_repo.list_by_picnic_product_ids(db, list(units_by_product)):
        if item.inventory_status is None:
            continue
        units = units_by_product[item.picnic_product_id]
        listr_inventory_service.adjust_count(db, item, units)
        restocked += units
    return restocked


def sync(
    db: Session,
    provider: PicnicProvider | None = None,
    deliveries: list[PicnicDelivery] | None = None,
    as_of: date | None = None,
) -> SyncResult:
    """Processes every delivery on or after the settings' `since` date that hasn't been yet.
    `deliveries` lets a caller that already fetched the summary (the order history page) skip a
    second call. A no-op while switched off."""
    provider = provider or picnic_provider
    settings = picnic_sync_repo.get_settings(db)
    result = SyncResult()
    if not settings.enabled or settings.since is None:
        return result
    session = picnic_session_repo.get(db)
    if session is None:
        raise PicnicSyncNotConnected()
    as_of = as_of or date.today()
    try:
        if deliveries is None:
            deliveries = provider.get_deliveries(session.auth_key)
        due = [d for d in deliveries if settings.since <= d.delivered_at.date() <= as_of]
        done = picnic_sync_repo.synced_by_id(db, [d.id for d in due])
        for delivery in sorted(due, key=lambda d: d.delivered_at):
            if delivery.id in done:
                continue
            detail = provider.get_delivery_detail(session.auth_key, delivery.id)
            delivered_on = delivery.delivered_at.date()
            booked = matched = 0
            if settings.gripr_account_id is not None and settings.gripr_category_id is not None:
                booked, matched = _book_orders(db, detail, delivered_on, settings.gripr_account_id, settings.gripr_category_id)
            restocked = _restock(db, detail)
            picnic_sync_repo.mark_synced(
                db, delivery.id, delivered_on, orders_booked=booked, orders_matched=matched, items_restocked=restocked
            )
            result.deliveries += 1
            result.orders_booked += booked
            result.orders_matched += matched
            result.items_restocked += restocked
    except PicnicAuthError:
        picnic_session_repo.clear(db)
        raise PicnicSyncNotConnected()
    settings.last_synced_at = datetime.now()
    db.flush()
    return result
