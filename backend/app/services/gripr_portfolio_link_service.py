"""Bridges gripr brokerage accounts and gainr portfolios -- the one place the two modules touch
each other. See docs/adr/0014 and docs/adr/0021 (generalized from one hardcoded link to a table
of account<->portfolio pairs, so a second gripr account can mirror a second gainr portfolio).

Two directions, deliberately different in kind:

- **Money in and out is a transaction.** A gripr transfer into a linked account is real money
  arriving at that broker, so it books a matching Deposit in its linked portfolio's cash ledger
  (and a transfer out books a Withdraw). The mirror is linked by `source_ref`, so editing or
  deleting the gripr transfer edits or deletes its gainr counterpart instead of orphaning it --
  the same reverse-then-reapply discipline `gripr_transaction_service` already uses for
  loan-linked categories.
- **Market movement is not.** Each linked account's balance is simply overwritten with its own
  portfolio's current value. A day's gain or loss is not money moving between accounts, so it
  must never become a ledger row; it's a correction to a stored balance, nothing more.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccount, GriprBalanceMode
from app.models.gripr_portfolio_link import GriprPortfolioLink
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.models.transaction import Transaction, TransactionType
from app.repositories import gripr_account_repo, gripr_portfolio_link_repo, transaction_repo
from app.services.performance_service import performance_service
from app.services.position_service import portfolio_value_eur

SOURCE_REF_PREFIX = "pefi_transfer:"


class PortfolioAlreadyLinkedError(Exception):
    """Raised when a portfolio is already mirrored by a different gripr account -- each side of
    the bridge is one-to-one, so linking a second account to it would leave two accounts both
    claiming to hold the same money."""


def linked_account(db: Session, portfolio_id: int) -> GriprAccount | None:
    link = gripr_portfolio_link_repo.get_by_portfolio(db, portfolio_id)
    if link is None:
        return None
    return gripr_account_repo.get_account(db, link.account_id)


def set_link(db: Session, account_id: int, portfolio_id: int | None) -> GriprPortfolioLink | None:
    """Points `account_id` at `portfolio_id` (replacing whatever it pointed at before), or clears
    its link entirely when `portfolio_id` is None. Immediately re-syncs that account's balance --
    linking or unlinking should show its effect straight away, not wait for the next daily run."""
    existing = gripr_portfolio_link_repo.get_by_account(db, account_id)
    if portfolio_id is None:
        if existing is not None:
            gripr_portfolio_link_repo.delete_link(db, existing)
        return None

    other = gripr_portfolio_link_repo.get_by_portfolio(db, portfolio_id)
    if other is not None and other.account_id != account_id:
        raise PortfolioAlreadyLinkedError(portfolio_id)

    if existing is not None:
        existing.portfolio_id = portfolio_id
        return existing
    return gripr_portfolio_link_repo.create_link(db, account_id, portfolio_id)


def _source_ref(gripr_txn_id: int) -> str:
    return f"{SOURCE_REF_PREFIX}{gripr_txn_id}"


def _mirror_shape(txn: GriprTransaction, account_id: int) -> tuple[TransactionType, Decimal] | None:
    """What this gripr transaction means for the given linked account's gainr cash, if anything.
    Only transfers count: income or an expense booked directly on the brokerage account (a
    dividend, a fee) is already in gainr's own ledger, and mirroring it would double-count it."""
    if txn.type != GriprTransactionType.TRANSFER:
        return None
    if txn.counter_account_id == account_id:
        return TransactionType.DEPOSIT, txn.amount
    if txn.account_id == account_id:
        return TransactionType.WITHDRAW, txn.amount
    return None


def _matching_link(db: Session, txn: GriprTransaction) -> tuple[GriprPortfolioLink, TransactionType, Decimal] | None:
    """Which linked account (if any) this transfer touches, and what it means for that account's
    own gainr portfolio. In practice at most one link ever matches a given transaction -- money
    moves between an ordinary bank account and a single linked broker, never directly between two
    linked brokers -- so only the first match is mirrored."""
    for link in gripr_portfolio_link_repo.list_links(db):
        shape = _mirror_shape(txn, link.account_id)
        if shape is not None:
            return link, shape[0], shape[1]
    return None


def sync_mirror(db: Session, txn: GriprTransaction) -> Transaction | None:
    """Brings the gainr side in line with this gripr transaction's current shape: creates,
    updates, or removes the mirrored cash movement. Safe to call for any gripr transaction --
    one that doesn't touch a linked account simply clears any mirror it used to have (e.g.
    a transfer edited to point at a different account)."""
    existing = transaction_repo.get_by_source_ref(db, _source_ref(txn.id))
    match = _matching_link(db, txn)

    if match is None:
        if existing is not None:
            transaction_repo.delete_transaction(db, existing)
            performance_service.invalidate_cache(existing.portfolio_id)
        return None

    link, type_, amount = match
    if existing is None:
        mirrored = transaction_repo.create_transaction(
            db,
            portfolio_id=link.portfolio_id,
            date=txn.date,
            type=type_,
            value_eur=amount,
            costs=Decimal(0),
            total_eur=amount,
            notes=f"Automatisch vanuit gripr: {txn.type.value.lower()} op {txn.date.isoformat()}",
            source_ref=_source_ref(txn.id),
        )
    else:
        mirrored = transaction_repo.update_transaction(
            db, existing, portfolio_id=link.portfolio_id, date=txn.date, type=type_, value_eur=amount, total_eur=amount
        )
    performance_service.invalidate_cache(mirrored.portfolio_id)
    return mirrored


def remove_mirror(db: Session, txn: GriprTransaction) -> None:
    existing = transaction_repo.get_by_source_ref(db, _source_ref(txn.id))
    if existing is not None:
        transaction_repo.delete_transaction(db, existing)
        performance_service.invalidate_cache(existing.portfolio_id)


def sync_balance(db: Session) -> dict[int, Decimal]:
    """Overwrites every linked account's stored balance with its own portfolio's current value --
    each link is independent, so one portfolio's market movement never touches another's linked
    account. Returns {account_id: new_balance} for whichever accounts are linked; empty when
    nothing is."""
    balances: dict[int, Decimal] = {}
    for link in gripr_portfolio_link_repo.list_links(db):
        account = gripr_account_repo.get_account(db, link.account_id)
        if account is None:
            continue
        value = portfolio_value_eur(db, link.portfolio_id)
        # Only a stored balance can hold a figure that isn't the sum of its own transactions --
        # a transactional account would recompute it straight back from the ledger on the next
        # read.
        account.balance_mode = GriprBalanceMode.MANUAL
        account.manual_balance = value.quantize(Decimal("0.01"))
        balances[account.id] = account.manual_balance
    db.flush()
    return balances
