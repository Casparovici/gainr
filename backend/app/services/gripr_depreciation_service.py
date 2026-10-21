"""Depreciation of manually valued assets (a car) through the transfer that funds its replacement.
See docs/adr/0034-gripr-depreciation.md.

A recurring transfer (say €121 a month into the depreciation fund) can say which assets it is the
depreciation of, and by how much each. When an occurrence books, those assets lose that much value
-- applied with the transaction's other side effects (loan balances, portfolio mirror), so a
pre-booked occurrence waits for its date and an edit or delete reverses what was applied.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccountType, GriprBalanceMode
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.models.gripr_recurring import GriprRecurrenceFrequency
from app.repositories import gripr_account_repo, gripr_depreciation_repo, gripr_recurring_repo

Item = tuple[int, Decimal]


class InvalidDepreciationError(ValueError):
    """A depreciation that can't be applied: not on a transfer, not a manually valued asset, or
    more than the transfer itself."""


def validate(db: Session, rule_type: GriprTransactionType, rule_amount: Decimal, items: list[Item]) -> list[Item]:
    if not items:
        return []
    if rule_type != GriprTransactionType.TRANSFER:
        raise InvalidDepreciationError("only a transfer can be the depreciation of an asset")
    seen: set[int] = set()
    for account_id, amount in items:
        account = gripr_account_repo.get_account(db, account_id)
        if account is None or account.type != GriprAccountType.ASSET or account.balance_mode != GriprBalanceMode.MANUAL:
            raise InvalidDepreciationError("depreciation applies to an asset account with a manually set value")
        if amount <= 0:
            raise InvalidDepreciationError("a depreciation amount must be more than zero")
        if account_id in seen:
            raise InvalidDepreciationError("each asset can be listed once per transfer")
        seen.add(account_id)
    if sum((a for _, a in items), Decimal(0)) > rule_amount:
        raise InvalidDepreciationError("the depreciation can't be more than the transfer itself")
    return items


def for_rule(db: Session, recurring_id: int) -> list[Item]:
    return [(d.account_id, d.amount) for d in gripr_depreciation_repo.for_rule(db, recurring_id)]


def set_for_rule(db: Session, rule, items: list[Item]) -> None:
    validate(db, rule.type, rule.amount, items)
    gripr_depreciation_repo.delete_for_rule(db, rule.id)
    for account_id, amount in items:
        gripr_depreciation_repo.add(db, account_id, amount, recurring_id=rule.id)


def attach(db: Session, txn: GriprTransaction, items: list[Item]) -> None:
    """Records, on a booked transaction, the depreciation it carries (a snapshot of the rule's)."""
    for account_id, amount in items:
        gripr_depreciation_repo.add(db, account_id, amount, transaction_id=txn.id)


def apply(db: Session, txn: GriprTransaction, sign: int) -> None:
    """Lowers (sign=1) or restores (sign=-1) the assets' values by what the transaction carries."""
    for row in gripr_depreciation_repo.for_transaction(db, txn.id):
        account = gripr_account_repo.get_account(db, row.account_id)
        if account is not None:
            account.manual_balance = account.manual_balance - sign * row.amount
    db.flush()


@dataclass(frozen=True)
class DepreciatingAsset:
    account_id: int
    name: str
    value: Decimal
    monthly: Decimal
    months_left: int | None


@dataclass(frozen=True)
class Fund:
    account_id: int
    name: str
    balance: Decimal
    assets_value: Decimal
    monthly: Decimal
    covers_pct: Decimal | None


def _per_month(rule, amount: Decimal) -> Decimal:
    """What `amount` per occurrence of the rule comes to per calendar month."""
    if rule.frequency == GriprRecurrenceFrequency.WEEKLY:
        return amount * 52 / 12 / rule.interval
    if rule.frequency == GriprRecurrenceFrequency.YEARLY:
        return amount / 12 / rule.interval
    return amount / rule.interval


def overview(db: Session) -> tuple[list[DepreciatingAsset], list[Fund]]:
    """Every asset an active recurring transfer depreciates, and every account those transfers fill,
    with how the fund compares to the value that's depreciating into it."""
    from app.services import gripr_account_service

    rules = [r for r in gripr_recurring_repo.list_recurring(db, include_inactive=False) if r.type == GriprTransactionType.TRANSFER]
    grouped = gripr_depreciation_repo.for_rules(db, [r.id for r in rules])
    balances = {ab.account.id: ab for ab in gripr_account_service.list_with_balances(db, include_archived=True)}
    monthly: dict[int, Decimal] = {}
    fund_assets: dict[int, set[int]] = {}
    fund_monthly: dict[int, Decimal] = {}
    for rule in rules:
        for row in grouped.get(rule.id, []):
            per_month = _per_month(rule, row.amount)
            monthly[row.account_id] = monthly.get(row.account_id, Decimal(0)) + per_month
            if rule.counter_account_id is not None:
                fund_assets.setdefault(rule.counter_account_id, set()).add(row.account_id)
                fund_monthly[rule.counter_account_id] = fund_monthly.get(rule.counter_account_id, Decimal(0)) + per_month
    assets = []
    for account_id, per_month in sorted(monthly.items()):
        ab = balances.get(account_id)
        if ab is None:
            continue
        months_left = int(ab.balance // per_month) if per_month > 0 and ab.balance > 0 else (0 if ab.balance <= 0 else None)
        assets.append(DepreciatingAsset(account_id, ab.account.name, ab.balance, per_month.quantize(Decimal("0.01")), months_left))
    value_of = {a.account_id: a.value for a in assets}
    funds = []
    for fund_id, asset_ids in sorted(fund_assets.items()):
        ab = balances.get(fund_id)
        if ab is None:
            continue
        total = sum((value_of.get(a, Decimal(0)) for a in asset_ids), Decimal(0))
        covers = (ab.balance / total * 100).quantize(Decimal("0.1")) if total > 0 else None
        funds.append(Fund(fund_id, ab.account.name, ab.balance, total, fund_monthly[fund_id].quantize(Decimal("0.01")), covers))
    return assets, funds
