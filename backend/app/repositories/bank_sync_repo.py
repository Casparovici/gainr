from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.models.bank_sync import BankConnection, BankCounterpartyRule, BankSyncAccount, BankSyncedTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType


# -- connections -------------------------------------------------------------------------------


def list_connections(db: Session) -> list[BankConnection]:
    return list(db.execute(select(BankConnection).order_by(BankConnection.id)).scalars().all())


def get_connection(db: Session, connection_id: int) -> BankConnection | None:
    return db.get(BankConnection, connection_id)


def get_connection_by_pending_state(db: Session, state: str) -> BankConnection | None:
    if not state:
        return None
    return db.execute(select(BankConnection).where(BankConnection.pending_state == state)).scalar_one_or_none()


def update_connection(db: Session, connection: BankConnection, **fields) -> BankConnection:
    for key, value in fields.items():
        setattr(connection, key, value)
    db.flush()
    return connection


@dataclass(frozen=True)
class FedAccount:
    gripr_account_id: int
    since: date
    # Its bank sends amounts only, so it can't tell who a transfer came from -- the other side has
    # to book it.
    amount_only: bool = False


def fed_accounts(db: Session) -> dict[str, FedAccount]:
    """Every account a switched-on bank is feeding, by IBAN: mapped to a gripr account, covered by
    the bank's current consent. Money between two of these is seen on both sides -- the sync books
    it once, from the outgoing side -- but only from the sending bank's own start date (before
    that, that bank isn't booking anything) and only if that bank can tell where the money went
    (an amount-only bank can't, so the side that can books it)."""
    query = (
        select(BankSyncAccount.iban, BankSyncAccount.gripr_account_id, BankConnection.since, BankConnection.amount_only)
        .join(BankConnection, BankConnection.id == BankSyncAccount.connection_id)
        .where(
            BankConnection.enabled.is_(True),
            BankConnection.since.is_not(None),
            BankSyncAccount.gripr_account_id.is_not(None),
            # An Enable Banking bank needs a live consent covering the account; Trading 212 is
            # read with the server's API key, no consent involved.
            (BankConnection.provider == "trading212")
            | (BankConnection.session_id.is_not(None) & BankSyncAccount.eb_uid.is_not(None)),
        )
    )
    return {iban: FedAccount(account_id, since, amount_only) for iban, account_id, since, amount_only in db.execute(query).all()}


def bank_fed_account_ids(db: Session) -> set[int]:
    """The gripr accounts whose transactions come from a bank while its sync is switched on -- a
    recurring rule on one of these lets the bank's row stand in for its own (see
    gripr_recurring_service.generate_due). Doesn't require a live consent: an expired one is
    reconnected and back-read, and the rule shouldn't book in the meantime.

    An amount-only bank (Trade Republic) doesn't count: its entries arrive two or more days late
    and can't name what they were, so its accounts' rules book on their own due date and the
    bank's entry checks the row off when it arrives."""
    query = (
        select(BankSyncAccount.gripr_account_id)
        .join(BankConnection, BankConnection.id == BankSyncAccount.connection_id)
        .where(
            BankConnection.enabled.is_(True),
            BankConnection.amount_only.is_(False),
            BankSyncAccount.gripr_account_id.is_not(None),
        )
    )
    return set(db.execute(query).scalars().all())


def rule_target_account_ids(db: Session) -> set[int]:
    """The gripr accounts a counterparty rule books transfers with -- money moving to or from them
    is recognisable in a bank's data even though the account itself isn't synced."""
    return set(db.execute(select(BankCounterpartyRule.gripr_account_id)).scalars().all())


# -- accounts ----------------------------------------------------------------------------------


def list_accounts(db: Session, connection_id: int | None = None) -> list[BankSyncAccount]:
    query = select(BankSyncAccount).order_by(BankSyncAccount.iban)
    if connection_id is not None:
        query = query.where(BankSyncAccount.connection_id == connection_id)
    return list(db.execute(query).scalars().all())


def get_account(db: Session, iban: str) -> BankSyncAccount | None:
    return db.get(BankSyncAccount, iban)


def upsert_account(db: Session, iban: str, **fields) -> BankSyncAccount:
    account = db.get(BankSyncAccount, iban)
    if account is None:
        account = BankSyncAccount(iban=iban)
        db.add(account)
    for key, value in fields.items():
        setattr(account, key, value)
    db.flush()
    return account


# -- counterparty rules ------------------------------------------------------------------------


def list_rules(db: Session) -> list[BankCounterpartyRule]:
    return list(db.execute(select(BankCounterpartyRule).order_by(BankCounterpartyRule.id)).scalars().all())


def get_rule(db: Session, rule_id: int) -> BankCounterpartyRule | None:
    return db.get(BankCounterpartyRule, rule_id)


def create_rule(db: Session, **fields) -> BankCounterpartyRule:
    rule = BankCounterpartyRule(**fields)
    db.add(rule)
    db.flush()
    return rule


def delete_rule(db: Session, rule: BankCounterpartyRule) -> None:
    db.delete(rule)
    db.flush()


# -- handled bank entries ----------------------------------------------------------------------


def handled_references(db: Session, references: list[str]) -> set[str]:
    if not references:
        return set()
    query = select(BankSyncedTransaction.reference).where(BankSyncedTransaction.reference.in_(references))
    return set(db.execute(query).scalars().all())


def record(
    db: Session,
    reference: str,
    iban: str,
    transacted_on: date,
    outcome: str,
    gripr_transaction_id: int | None = None,
    recurring_id: int | None = None,
    merchant: str | None = None,
) -> BankSyncedTransaction:
    row = BankSyncedTransaction(
        reference=reference,
        iban=iban,
        transacted_on=transacted_on,
        synced_at=datetime.now(),
        outcome=outcome,
        gripr_transaction_id=gripr_transaction_id,
        recurring_id=recurring_id,
        merchant=merchant or None,
    )
    db.add(row)
    db.flush()
    return row


def learned_category(db: Session, merchant: str) -> int | None:
    """The category of the reader's most recent card payment at `merchant` (normalised) -- whether
    the sync booked that row and the reader categorised it afterwards, or the payment matched a row
    the reader had entered themselves. Only expenses count: a refund from a shop never teaches its
    purchases a category."""
    query = (
        select(GriprTransaction.category_id)
        .join(BankSyncedTransaction, BankSyncedTransaction.gripr_transaction_id == GriprTransaction.id)
        .where(
            BankSyncedTransaction.merchant == merchant,
            GriprTransaction.category_id.is_not(None),
            GriprTransaction.type == GriprTransactionType.EXPENSE,
        )
        .order_by(BankSyncedTransaction.transacted_on.desc(), BankSyncedTransaction.synced_at.desc())
        .limit(1)
    )
    return db.execute(query).scalar_one_or_none()


def find_unclaimed_match(
    db: Session,
    account_id: int,
    amount: Decimal,
    is_debit: bool,
    around: date,
    days: int,
    booked_prefixes: list[str],
    pots: set[int] | frozenset[int] = frozenset(),
) -> GriprTransaction | None:
    """A row already in gripr that is this bank entry: the same amount moving the same way on
    `account_id` (money out = an expense from it or a transfer out of it; money in = income or a
    refund on it, or a transfer into it), dated within `days` of `around`, and neither booked nor
    already claimed by the banks in `booked_prefixes`. Closest-dated first. This is how something
    entered by hand -- or booked by the Picnic sync -- is recognised instead of booked twice. An
    amount-only bank passes just its own prefix, so a transfer the other bank booked (and claimed
    for its own half) is still there for this bank's half to claim.

    `pots` are the virtual pots inside `account_id`: what's spent from or paid into a pot is the
    account's own money at the bank, so it counts; money moving between the account and its pots
    never reaches the bank, so it never does -- otherwise a €75 card payment could be "matched"
    to the €75 set aside for car maintenance and never booked."""
    T = GriprTransactionType
    home = {account_id, *pots}
    outside = lambda column: column.is_(None) | column.not_in(home)  # noqa: E731
    if is_debit:
        shape = (GriprTransaction.account_id.in_(home) & (GriprTransaction.type == T.EXPENSE)) | (
            GriprTransaction.account_id.in_(home) & (GriprTransaction.type == T.TRANSFER) & outside(GriprTransaction.counter_account_id)
        )
    else:
        shape = (GriprTransaction.account_id.in_(home) & GriprTransaction.type.in_([T.INCOME, T.REFUND])) | (
            GriprTransaction.counter_account_id.in_(home) & (GriprTransaction.type == T.TRANSFER) & outside(GriprTransaction.account_id)
        )
    claimed_by = BankSyncedTransaction.reference.startswith(f"{booked_prefixes[0]}:") if booked_prefixes else false()
    for prefix in booked_prefixes[1:]:
        claimed_by = claimed_by | BankSyncedTransaction.reference.startswith(f"{prefix}:")
    claimed = select(BankSyncedTransaction.gripr_transaction_id).where(
        BankSyncedTransaction.gripr_transaction_id.is_not(None), claimed_by
    )
    query = select(GriprTransaction).where(
        shape,
        GriprTransaction.amount == amount,
        GriprTransaction.date >= around - timedelta(days=days),
        GriprTransaction.date <= around + timedelta(days=days),
        GriprTransaction.id.not_in(claimed),
    )
    candidates = [
        t for t in db.execute(query).scalars().all()
        if not (t.source_ref and any(t.source_ref.startswith(f"{p}:") for p in booked_prefixes))
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda t: (abs((t.date - around).days), t.id))


def find_unfiled_amount_only_entry(
    db: Session,
    account_ids: set[int],
    amount: Decimal,
    type_: GriprTransactionType,
    around: date,
    days: int,
    prefixes: list[str],
) -> tuple[GriprTransaction, BankSyncedTransaction] | None:
    """The row an amount-only bank booked for a payment the reader hasn't entered or filed yet:
    booked as is (not matched, not a rule's), still uncategorised, not already claimed by a hand
    entry. Closest-dated first -- the bank dates it a few days after the purchase."""
    if not prefixes:
        return None
    from_bank = BankSyncedTransaction.reference.startswith(f"{prefixes[0]}:")
    for prefix in prefixes[1:]:
        from_bank = from_bank | BankSyncedTransaction.reference.startswith(f"{prefix}:")
    query = (
        select(GriprTransaction, BankSyncedTransaction)
        .join(BankSyncedTransaction, BankSyncedTransaction.gripr_transaction_id == GriprTransaction.id)
        .where(
            from_bank,
            BankSyncedTransaction.outcome == "booked",
            GriprTransaction.account_id.in_(account_ids),
            GriprTransaction.type == type_,
            GriprTransaction.amount == amount,
            GriprTransaction.category_id.is_(None),
            GriprTransaction.date >= around - timedelta(days=days),
            GriprTransaction.date <= around + timedelta(days=days),
        )
    )
    rows = db.execute(query).all()
    if not rows:
        return None
    row, record = min(rows, key=lambda r: (abs((r[0].date - around).days), r[0].id))
    return row, record


def merchant_of(db: Session, transaction_id: int) -> str | None:
    """The counterparty key the bank sync recorded for this gripr transaction, if it came from (or
    was matched to) a bank entry."""
    query = (
        select(BankSyncedTransaction.merchant)
        .where(BankSyncedTransaction.gripr_transaction_id == transaction_id, BankSyncedTransaction.merchant.is_not(None))
        .limit(1)
    )
    return db.execute(query).scalar_one_or_none()


def uncategorised_from_merchant(
    db: Session, merchant: str, type_: GriprTransactionType, exclude_id: int
) -> list[GriprTransaction]:
    """Other bank-synced transactions of this type from the same counterparty that still have no
    category -- what "apply to similar" offers to file. Ones the reader categorised are left alone."""
    query = (
        select(GriprTransaction)
        .join(BankSyncedTransaction, BankSyncedTransaction.gripr_transaction_id == GriprTransaction.id)
        .where(
            BankSyncedTransaction.merchant == merchant,
            GriprTransaction.category_id.is_(None),
            GriprTransaction.type == type_,
            GriprTransaction.id != exclude_id,
        )
        .order_by(GriprTransaction.date.desc())
    )
    return list(db.execute(query).scalars().unique().all())
