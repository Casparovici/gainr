"""Bank transactions into gripr: every booked entry on a mapped account at a switched-on bank (ING,
Trade Republic, Trading 212) becomes a gripr row the reader only has to categorise -- once per bank
entry. See docs/adr/0029-ing-transactions-into-gripr.md, and docs/adr/0031-trading212-sync.md for
Trading 212, which is read through its own API instead of Enable Banking.

Each new bank entry, oldest first and across every bank at once, is handled by the first of these
that applies:

1. The incoming half of a transfer between two fed accounts (at the same bank or another one) is
   skipped: the outgoing half, seen on the other account, books the transfer once.
2. A row already in gripr for it -- entered by hand, or booked by the Picnic sync -- is claimed
   instead of booking a second one (same amount, same direction, within MATCH_DAYS).
3. It fulfils a recurring rule on that account: due within BANK_FULFIL_DAYS, amount within
   FULFIL_TOLERANCE of the rule's. It's booked for what the bank actually moved, filed under the
   rule's category, and the rule moves on to its next occurrence. (Such rules no longer book
   their own rows -- see gripr_recurring_service.generate_due.)
4. Otherwise it's booked: as a transfer when the counterparty is one of the reader's own
   accounts (a fed account, or a counterparty rule), else as an expense or income, with the
   counterparty and description in the notes -- uncategorised, except a card payment at a merchant
   the reader has categorised before (Trading 212 names the merchant), which takes that category.
"""

import hmac
import re
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app import config
from app.models.bank_sync import BankConnection, BankCounterpartyRule, BankSyncAccount
from app.models.gripr_recurring import GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.repositories import bank_sync_repo, broker_sync_repo, gripr_account_repo, gripr_portfolio_link_repo, gripr_recurring_repo
from app.repositories.bank_sync_repo import FedAccount
from app.services import gripr_receivable_service, gripr_recurring_service, gripr_transaction_service
from app.services.enablebanking_provider import (
    BankTransaction,
    EnableBankingError,
    EnableBankingProvider,
    EnableBankingRateLimitError,
    EnableBankingSessionError,
    enablebanking_provider,
)
from app.services.gripr_recurring_service import BANK_FULFIL_DAYS
from app.services.trading212_provider import (
    CashEntry,
    Trading212AuthError,
    Trading212Error,
    Trading212Provider,
    trading212_provider,
)

# A consent is asked for this much less than the bank's own maximum (ING 180 days, Trade Republic
# 90), leaving room for clock skew -- a request for longer than the maximum is refused outright.
CONSENT_MARGIN = timedelta(days=1)
# Used when Enable Banking's bank list doesn't say: the shortest maximum seen so far.
FALLBACK_CONSENT = timedelta(days=89)
# How far apart a hand-entered row and the bank entry it records may be dated -- hand entries
# land on the day of the purchase, the bank's on the day it was processed.
MATCH_DAYS = 7
# How far a bank entry's amount may stray from its recurring rule's and still be that rule's
# occurrence -- a salary or an energy bill moves a little month to month.
FULFIL_TOLERANCE = Decimal("0.10")
# Each run re-reads this far back from the last one, so an entry a bank books a few days late (a
# weekend, a card settlement) is still picked up. Already-handled entries are skipped by reference.
REFETCH_OVERLAP_DAYS = 7
# An amount-only bank's entry is only handled this long after the bank booked it, so whatever it
# gets checked against is in gripr first: the reader's own hand entry (typed in a day or two after
# the purchase settles), or the other bank's half of a transfer. Re-reading REFETCH_OVERLAP_DAYS
# back each run picks it up once it's due.
AMOUNT_ONLY_GRACE_DAYS = 2
# How far from an amount rule's day of the month a matching entry may fall (a savings plan on
# the 2nd executes a day or two later around a weekend).
RULE_DAY_WINDOW = 3
NOTES_LIMIT = 500
# BankConnection.provider for Trading 212, read with an API key rather than a consent.
TRADING212 = "trading212"
# The gainr broker whose portfolio's linked gripr account shares Trading 212's cash.
TRADING212_BROKER = "Trading212"

T = GriprTransactionType


class BankNotConfigured(Exception):
    """The Enable Banking app id, key or redirect URL isn't set on this server."""


class BankStateMismatch(Exception):
    """A callback that doesn't carry the state any pending consent was started with."""


@dataclass
class SyncResult:
    booked: int = 0
    matched: int = 0
    fulfilled: int = 0
    counterparts: int = 0
    # Bank name -> what went wrong there; the other banks still synced.
    problems: dict[str, str] = field(default_factory=dict)


def enablebanking_configured(provider: EnableBankingProvider | None = None) -> bool:
    provider = provider or enablebanking_provider
    return provider.configured and bool(config.ING_REDIRECT_URL)


def is_configured(provider: EnableBankingProvider | None = None, t212: Trading212Provider | None = None) -> bool:
    """Whether this server can read any bank at all: Enable Banking set up, or a Trading 212 key."""
    return enablebanking_configured(provider) or (t212 or trading212_provider).configured


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_connected(connection: BankConnection, now: datetime | None = None, t212: Trading212Provider | None = None) -> bool:
    """Whether the bank can be read right now: a live consent, or -- for Trading 212, which has
    none -- an API key on the server."""
    if connection.provider == TRADING212:
        return (t212 or trading212_provider).configured
    return (
        connection.session_id is not None
        and connection.valid_until is not None
        and connection.valid_until > (now or _utcnow())
    )


def _prefixes(db: Session) -> list[str]:
    return [c.source_prefix for c in bank_sync_repo.list_connections(db)]


# -- connecting --------------------------------------------------------------------------------


def start_connect(
    db: Session, connection: BankConnection, provider: EnableBankingProvider | None = None, now: datetime | None = None
) -> str:
    """Starts a consent at the connection's bank and returns the URL to send the reader to. The
    state it's started with is kept so the callback can prove which consent it belongs to."""
    provider = provider or enablebanking_provider
    if connection.provider == TRADING212 or not enablebanking_configured(provider):
        raise BankNotConfigured()
    maximum = provider.maximum_consent_seconds(connection.aspsp_name, connection.aspsp_country)
    validity = timedelta(seconds=maximum) - CONSENT_MARGIN if maximum else FALLBACK_CONSENT
    state = secrets.token_urlsafe(24)
    bank_sync_repo.update_connection(db, connection, pending_state=state)
    return provider.start_authorization(
        aspsp_name=connection.aspsp_name,
        country=connection.aspsp_country,
        redirect_url=config.ING_REDIRECT_URL,
        state=state,
        valid_until=(now or datetime.now(timezone.utc)) + validity,
    )


def complete_connect(db: Session, state: str, code: str, provider: EnableBankingProvider | None = None) -> BankConnection:
    """Finishes the consent a bank redirected back from: finds the connection it was started for
    by its state, turns the code into a session and records every account it covers, keeping the
    gripr account each was already mapped to. That bank's previous session, if any, is closed at
    Enable Banking -- one live consent per bank."""
    provider = provider or enablebanking_provider
    connection = bank_sync_repo.get_connection_by_pending_state(db, state)
    if connection is None or not hmac.compare_digest(connection.pending_state or "", state):
        raise BankStateMismatch()
    session = provider.create_session(code)
    previous = connection.session_id
    bank_sync_repo.update_connection(
        db, connection, session_id=session.session_id, valid_until=session.valid_until, pending_state=None, last_error=None
    )
    covered = {a.iban for a in session.accounts}
    for account in session.accounts:
        bank_sync_repo.upsert_account(
            db, account.iban, connection_id=connection.id, eb_uid=account.uid, product=account.product, holder_name=account.holder_name
        )
    for account in bank_sync_repo.list_accounts(db, connection.id):
        if account.iban not in covered:
            account.eb_uid = None
    if previous and previous != session.session_id:
        try:
            provider.delete_session(previous)
        except EnableBankingError:
            pass  # it expires on its own; nothing reads it any more
    db.flush()
    return connection


def disconnect(db: Session, connection: BankConnection, provider: EnableBankingProvider | None = None) -> None:
    """Ends the bank's consent and switches it off, so recurring rules on its accounts book their
    own rows again. The account mapping and rules are kept for a later reconnect."""
    provider = provider or enablebanking_provider
    if connection.provider == TRADING212:
        # Nothing to end at Trading 212 -- the key lives in the server's environment.
        bank_sync_repo.update_connection(db, connection, enabled=False)
        return
    if connection.session_id:
        try:
            provider.delete_session(connection.session_id)
        except EnableBankingError:
            pass
    bank_sync_repo.update_connection(db, connection, session_id=None, valid_until=None, pending_state=None, enabled=False)
    for account in bank_sync_repo.list_accounts(db, connection.id):
        account.eb_uid = None
    db.flush()


# -- recognising the reader's own accounts -----------------------------------------------------


def normalize_text(value: str) -> str:
    """Case-, space- and punctuation-insensitive form for "contains" matching -- so the savings
    number the reader typed as "B 145-58977" finds "Oranje spaarrekening B14558977"."""
    return re.sub(r"[^0-9a-z]", "", value.casefold())


def normalize_iban(value: str) -> str:
    return re.sub(r"\s", "", value).upper()


def normalize_merchant(value: str) -> str:
    return normalize_text(value)[:120]


def trading212_entries(entries: list[CashEntry]) -> list[BankTransaction]:
    """The part of Trading 212's cash activity that is the card account's own: card payments,
    with the merchant, and money moving in or out (a top-up from ING, a withdrawal back to it).
    Interest and spending cashback are gainr's -- booked there as a weekly deposit, next to the
    auto-invest buys they pay for -- and so are trades, dividends and currency conversions."""
    transactions: list[BankTransaction] = []
    for entry in entries:
        action = entry.action.casefold()
        if action.startswith("card"):
            anonymous = False
        elif action in ("deposit", "withdrawal"):
            anonymous = True
        else:
            continue
        if entry.amount == 0:
            continue
        day = entry.local_date
        if anonymous:
            description = f"Trading 212 {action}"
        else:
            description = entry.merchant_category.replace("_", " ").capitalize()
        transactions.append(
            BankTransaction(
                reference=entry.entry_id,
                amount=abs(entry.amount),
                currency=entry.currency,
                is_debit=entry.amount < 0,
                booked_on=day,
                transacted_on=day,
                counterparty_name=entry.merchant,
                counterparty_iban=None,
                description=description,
                method=entry.action,
                raw_text=f"{entry.merchant} {entry.merchant_category}".strip(),
                anonymous=anonymous,
                merchant=normalize_merchant(entry.merchant) if entry.merchant else "",
            )
        )
    return transactions


def _days_from_day_of_month(day: date, day_of_month: int) -> int:
    """Distance from `day` to the nearest date carrying `day_of_month`, this month or a
    neighbouring one -- "the 2nd" is one day from 1 Oct and from 3 Oct alike, and two days from
    30 Sep."""
    candidates = []
    for month_shift in (-1, 0, 1):
        year, month = day.year, day.month + month_shift
        if month == 0:
            year, month = year - 1, 12
        elif month == 13:
            year, month = year + 1, 1
        try:
            candidates.append(date(year, month, day_of_month))
        except ValueError:
            continue  # the 31st in a 30-day month
    return min(abs((c - day).days) for c in candidates)


def _rule_matches(rule: BankCounterpartyRule, txn: BankTransaction) -> bool:
    if rule.iban and normalize_iban(rule.iban) != (txn.counterparty_iban or ""):
        return False
    if rule.text_contains:
        needle = normalize_text(rule.text_contains)
        if not needle or needle not in normalize_text(f"{txn.counterparty_name} {txn.raw_text}"):
            return False
    if rule.amount is not None and txn.amount != rule.amount:
        return False
    if rule.amount_max is not None and txn.amount > rule.amount_max:
        return False
    if rule.day_of_month is not None and _days_from_day_of_month(txn.transacted_on, rule.day_of_month) > RULE_DAY_WINDOW:
        return False
    if rule.direction is not None and rule.direction != ("out" if txn.is_debit else "in"):
        return False
    return bool(rule.iban or rule.text_contains or rule.amount is not None or rule.amount_max is not None)


def _amount_only_rule(rule: BankCounterpartyRule) -> bool:
    return not rule.iban and not rule.text_contains


def own_account_for(
    txn: BankTransaction, fed: dict[str, FedAccount], rules: list[BankCounterpartyRule], amount_only: bool = False
) -> int | None:
    """The gripr account on the other side when the counterparty is the reader's own: a fed
    account at any bank (by IBAN), else the most specific counterparty rule that matches (one
    matching on more fields beats one matching on fewer -- a payment processor's IBAN is shared by
    many merchants).

    A rule that matches on nothing but amount and date is only for a bank that sends nothing else
    (`amount_only`, Trade Republic). A bank that names the other side (ING, a Trading 212 card
    payment) would otherwise have a €8 Jumbo payment on the 2nd read as the €15-ceiling saveback."""
    if txn.counterparty_iban and txn.counterparty_iban in fed:
        return fed[txn.counterparty_iban].gripr_account_id
    if not amount_only:
        rules = [r for r in rules if not _amount_only_rule(r)]

    def specificity(rule: BankCounterpartyRule) -> int:
        fields = (rule.iban, rule.text_contains, rule.amount, rule.amount_max, rule.day_of_month, rule.direction)
        return sum(v is not None and v != "" for v in fields)

    for rule in sorted(rules, key=lambda r: (-specificity(r), r.id)):
        if _rule_matches(rule, txn):
            return rule.gripr_account_id
    return None


def notes_for(txn: BankTransaction, bank_name: str, amount_only: bool = False, transfer: bool = False) -> str:
    parts = [p for p in (txn.counterparty_name, txn.description) if p]
    if len(parts) == 2 and normalize_text(parts[0]) == normalize_text(parts[1]):
        parts = parts[:1]
    if not parts and amount_only:
        if transfer:
            return f"{bank_name}: transfer recognised by its amount and date"
        # Nothing to say what it was -- which is the point: it's an entry the reader didn't type in.
        return f"{bank_name}: not entered by hand — look it up in the {bank_name} app"
    return (" — ".join(parts) or txn.method or bank_name)[:NOTES_LIMIT]


# -- recurring rules ---------------------------------------------------------------------------


def _rule_direction_matches(rule: GriprRecurringTransaction, account_id: int, is_debit: bool, homes: dict[int, int]) -> bool:
    """Whether the rule moves money the way this bank entry does on `account_id` -- a rule on a
    virtual pot inside the account counts as the account's own (`homes`: pot -> account)."""
    def home(x: int | None) -> int | None:
        return homes.get(x, x) if x is not None else None

    if rule.type == T.TRANSFER:
        return home(rule.account_id) == account_id if is_debit else home(rule.counter_account_id) == account_id
    if home(rule.account_id) != account_id:
        return False
    return (rule.type == T.EXPENSE) == is_debit


def _name_hit(rule: GriprRecurringTransaction, txn: BankTransaction) -> bool:
    haystack = normalize_text(f"{txn.counterparty_name} {txn.description}")
    return any(len(token) >= 4 and token in haystack for token in (normalize_text(w) for w in rule.name.split()))


def find_fulfilled_rule(
    rules: list[GriprRecurringTransaction],
    account_id: int,
    txn: BankTransaction,
    other_account_id: int | None,
    homes: dict[int, int] | None = None,
) -> GriprRecurringTransaction | None:
    """The recurring rule whose current occurrence this bank entry is, if any: same account and
    direction, due within BANK_FULFIL_DAYS, amount within FULFIL_TOLERANCE. A rule whose name
    shows up in the counterparty or description wins over one that merely fits, then the closest
    amount, then the closest date -- two €10 charity debits a few days apart go to the right
    rule. A transfer the bank already recognises as one only fulfils a transfer rule, and the
    other way round."""
    best: tuple | None = None
    for rule in rules:
        if not _rule_direction_matches(rule, account_id, txn.is_debit, homes or {}):
            continue
        if (other_account_id is not None) != (rule.type == T.TRANSFER):
            continue
        gap = abs((rule.next_due_date - txn.transacted_on).days)
        diff = abs(txn.amount - rule.amount)
        if gap > BANK_FULFIL_DAYS or diff > rule.amount * FULFIL_TOLERANCE:
            continue
        score = (not _name_hit(rule, txn), diff, gap, rule.id)
        if best is None or score < best[0]:
            best = (score, rule)
    return best[1] if best else None


# -- syncing -----------------------------------------------------------------------------------


@dataclass
class _Context:
    db: Session
    fed: dict[str, FedAccount]
    rules: list[BankCounterpartyRule]
    recurring: list[GriprRecurringTransaction]
    prefixes: list[str]
    # Virtual pot -> the account it sits inside.
    homes: dict[int, int]
    result: SyncResult
    # A bank account -> other gripr accounts whose money is the same cash at that bank, so a
    # transfer between them never shows up there: T212 Debit and the investment account linked to
    # the gainr portfolio Trading 212 books into (one cash balance at Trading 212).
    shared_cash: dict[int, set[int]] = field(default_factory=dict)


def _book(
    db: Session,
    txn: BankTransaction,
    reference: str,
    connection: BankConnection,
    account_id: int,
    other_account_id: int | None,
    rule: GriprRecurringTransaction | None = None,
) -> GriprTransaction:
    """A new gripr row for the bank entry, through the transaction service so a loan-linked
    category or a portfolio-linked account gets its usual side effects."""
    if rule is not None and rule.type == T.TRANSFER:
        other_account_id = other_account_id or (rule.counter_account_id if txn.is_debit else rule.account_id)
        # The rule's own side on this bank's account -- the account itself, or a pot inside it.
        account_id = rule.account_id if txn.is_debit else rule.counter_account_id
    elif rule is not None:
        account_id = rule.account_id  # the account, or the pot inside it the rule is paid from
    notes = notes_for(txn, connection.aspsp_name, connection.amount_only, transfer=other_account_id is not None)
    fields: dict = dict(date=txn.transacted_on, amount=txn.amount, notes=notes, source_ref=reference)
    if other_account_id is not None:
        source, target = (account_id, other_account_id) if txn.is_debit else (other_account_id, account_id)
        fields.update(type=T.TRANSFER, account_id=source, counter_account_id=target)
    elif rule is not None:
        fields.update(type=rule.type, account_id=account_id, category_id=rule.category_id)
    else:
        fields.update(type=T.EXPENSE if txn.is_debit else T.INCOME, account_id=account_id)
        if txn.is_debit and txn.merchant:
            fields.update(category_id=bank_sync_repo.learned_category(db, txn.merchant))
    return gripr_transaction_service.create_transaction(db, **fields)


def _handle(ctx: _Context, connection: BankConnection, account: BankSyncAccount, txn: BankTransaction) -> None:
    db, result = ctx.db, ctx.result
    reference = f"{connection.source_prefix}:{txn.reference}"
    account_id = account.gripr_account_id
    other = own_account_for(txn, ctx.fed, ctx.rules, connection.amount_only)
    if other == account_id:
        other = None

    twin = ctx.fed.get(txn.counterparty_iban or "")
    if (
        not txn.is_debit
        and twin is not None
        and not twin.amount_only
        and twin.gripr_account_id != account_id
        and txn.transacted_on >= twin.since
    ):
        # The outgoing half, on the other fed account, books this transfer (or claims the row
        # entered for it) -- booking this half too would move the money twice.
        bank_sync_repo.record(db, reference, account.iban, txn.transacted_on, "counterpart")
        result.counterparts += 1
        return

    # A row another bank booked counts as "already there" for an amount-only bank, or an entry
    # that doesn't say who's on the other side: it's how the Trade Republic half of a transfer, or
    # a Trading 212 top-up, finds the row the ING half booked.
    not_mine = [connection.source_prefix] if connection.amount_only or txn.anonymous else ctx.prefixes
    pots = {pot for pot, parent in ctx.homes.items() if parent == account_id} | ctx.shared_cash.get(account_id, set())
    existing = bank_sync_repo.find_unclaimed_match(
        db, account_id, txn.amount, txn.is_debit, txn.transacted_on, MATCH_DAYS, not_mine, pots
    )
    if existing is not None:
        # The bank says it happened: a pre-booked occurrence it stands for gets its loan/portfolio
        # effects now, if its own due date hasn't already brought them.
        if existing.date <= date.today():
            gripr_transaction_service.apply_effects(db, existing)
        bank_sync_repo.record(db, reference, account.iban, txn.transacted_on, "matched", existing.id, merchant=txn.merchant)
        result.matched += 1
        return

    rule = find_fulfilled_rule(ctx.recurring, account_id, txn, other, ctx.homes)
    if rule is not None:
        booked = _book(db, txn, reference, connection, account_id, other, rule)
        rule.next_due_date = gripr_recurring_service.advance(rule.frequency, rule.next_due_date, rule.interval)
        bank_sync_repo.record(db, reference, account.iban, txn.transacted_on, "fulfilled", booked.id, rule.id, merchant=txn.merchant)
        result.fulfilled += 1
        return

    if not txn.is_debit and other is None and not connection.amount_only and not txn.anonymous:
        # Someone paying back what the reader fronted (a Tikkie for last week's dinner): booked as
        # a refund on that expense when its "from" names this payer and only that expense fits.
        expense = gripr_receivable_service.match_incoming(db, f"{txn.counterparty_name} {txn.description}", txn.amount)
        if expense is not None:
            booked = gripr_transaction_service.create_transaction(
                db, date=txn.transacted_on, amount=txn.amount, type=T.REFUND, account_id=account_id,
                refund_of_id=expense.id, notes=notes_for(txn, connection.aspsp_name), source_ref=reference,
            )
            bank_sync_repo.record(db, reference, account.iban, txn.transacted_on, "booked", booked.id)
            result.booked += 1
            return

    booked = _book(db, txn, reference, connection, account_id, other)
    bank_sync_repo.record(db, reference, account.iban, txn.transacted_on, "booked", booked.id, merchant=txn.merchant)
    result.booked += 1


def _fetch(
    db: Session,
    connection: BankConnection,
    provider: EnableBankingProvider,
    t212: Trading212Provider,
    as_of: date,
    result: SyncResult,
) -> list[tuple[BankSyncAccount, BankTransaction]] | None:
    """One bank's entries since its last run (or its start date), or None when it can't be read
    right now -- the reason recorded on the connection and in the result, the other banks
    unaffected."""
    if not is_connected(connection, t212=t212):
        result.problems[connection.aspsp_name] = "not configured" if connection.provider == TRADING212 else "not connected"
        return None
    date_from = connection.since
    if connection.last_synced_at is not None:
        date_from = max(connection.since, connection.last_synced_at.date() - timedelta(days=REFETCH_OVERLAP_DAYS))
    if date_from > as_of:
        return []  # switched on from a date still to come -- nothing to fetch yet (banks refuse one)
    if connection.provider == TRADING212:
        return _fetch_trading212(db, connection, t212, date_from, result)
    accounts = [a for a in bank_sync_repo.list_accounts(db, connection.id) if a.gripr_account_id is not None and a.eb_uid]
    fetched: list[tuple[BankSyncAccount, BankTransaction]] = []
    try:
        for account in accounts:
            for txn in provider.get_transactions(connection.session_id, account.eb_uid, account.iban, date_from):
                fetched.append((account, txn))
    except EnableBankingRateLimitError:
        message = (
            f"{connection.aspsp_name} allows only a few reads a day and refused this one; "
            "trying again in tomorrow morning's run."
        )
        bank_sync_repo.update_connection(db, connection, last_error=message)
        result.problems[connection.aspsp_name] = "daily read limit reached"
        return None
    except EnableBankingSessionError:
        message = f"The {connection.aspsp_name} consent expired or was revoked."
        bank_sync_repo.update_connection(db, connection, session_id=None, valid_until=None, last_error=message)
        result.problems[connection.aspsp_name] = "consent expired or revoked"
        return None
    except EnableBankingError as exc:
        bank_sync_repo.update_connection(db, connection, last_error=f"Couldn't reach {connection.aspsp_name}; retrying next run.")
        result.problems[connection.aspsp_name] = str(exc)[:200]
        return None
    return fetched


def _fetch_trading212(
    db: Session, connection: BankConnection, t212: Trading212Provider, date_from: date, result: SyncResult
) -> list[tuple[BankSyncAccount, BankTransaction]] | None:
    """Trading 212 has one account, holding both the investments and the card's cash; only its card
    payments and top-ups/withdrawals land in gripr (see trading212_entries)."""
    accounts = [a for a in bank_sync_repo.list_accounts(db, connection.id) if a.gripr_account_id is not None]
    if not accounts:
        return []
    try:
        entries = t212.cash_activity(date_from)
    except Trading212AuthError:
        message = "Trading 212 refused the API key. Check it's still valid and allowed from this server's IP address."
        bank_sync_repo.update_connection(db, connection, last_error=message)
        result.problems[connection.aspsp_name] = "API key refused"
        return None
    except Trading212Error as exc:
        bank_sync_repo.update_connection(db, connection, last_error=f"Couldn't reach {connection.aspsp_name}; retrying next run.")
        result.problems[connection.aspsp_name] = str(exc)[:200]
        return None
    return [(accounts[0], txn) for txn in trading212_entries(entries)]


def _shared_cash(db: Session, connections: list[BankConnection]) -> dict[int, set[int]]:
    """For a fed Trading 212 account: the gripr account linked to the gainr portfolio its broker
    sync books into. Both are the same cash at Trading 212, so money between them (T212 Debit ->
    Beleggen when the reader invests) is never a Trading 212 entry, and mustn't be matched by one."""
    shared: dict[int, set[int]] = {}
    broker = broker_sync_repo.get_connection(db, TRADING212_BROKER)
    link = gripr_portfolio_link_repo.get_by_portfolio(db, broker.portfolio_id) if broker and broker.portfolio_id else None
    if link is None:
        return shared
    for connection in connections:
        if connection.provider != TRADING212:
            continue
        for account in bank_sync_repo.list_accounts(db, connection.id):
            if account.gripr_account_id is not None and account.gripr_account_id != link.account_id:
                shared.setdefault(account.gripr_account_id, set()).add(link.account_id)
    return shared


def sync(
    db: Session,
    provider: EnableBankingProvider | None = None,
    as_of: date | None = None,
    t212: Trading212Provider | None = None,
    scheduled: bool = False,
) -> SyncResult:
    """Fetches every switched-on bank's booked entries since its last run and handles the ones not
    seen before, oldest first across all banks. A bank that can't be read is reported in the
    result and skipped; the others still sync.

    An amount-only bank (Trade Republic) is only read by the `scheduled` morning run: it allows a
    few reads a day, and its entries wait two days before they're handled anyway, so reading it
    again on "Sync now" would only use up those reads."""
    provider = provider or enablebanking_provider
    t212 = t212 or trading212_provider
    as_of = as_of or date.today()
    result = SyncResult()
    connections = [
        c for c in bank_sync_repo.list_connections(db)
        if c.enabled and c.since is not None and (scheduled or not c.amount_only)
    ]
    if not connections:
        return result

    fetched: list[tuple[BankConnection, BankSyncAccount, BankTransaction]] = []
    succeeded: list[BankConnection] = []
    for connection in connections:
        entries = _fetch(db, connection, provider, t212, as_of, result)
        if entries is None:
            continue
        succeeded.append(connection)
        fetched.extend((connection, account, txn) for account, txn in entries)

    handled = bank_sync_repo.handled_references(db, [f"{c.source_prefix}:{t.reference}" for c, _, t in fetched])
    bank_fed = bank_sync_repo.bank_fed_account_ids(db)
    recognisable = bank_fed | bank_sync_repo.rule_target_account_ids(db)
    homes = gripr_account_repo.pot_parents(db)
    ctx = _Context(
        db=db,
        fed=bank_sync_repo.fed_accounts(db),
        rules=bank_sync_repo.list_rules(db),
        recurring=[
            r for r in gripr_recurring_repo.list_recurring(db, include_inactive=False)
            if gripr_recurring_service.is_bank_fed(r, bank_fed, recognisable, homes)
        ],
        prefixes=_prefixes(db),
        homes=homes,
        result=result,
        shared_cash=_shared_cash(db, connections),
    )
    # On the same day: banks that can tell who the money went to before amount-only ones, and
    # outgoing before incoming -- so a transfer is booked by the half that knows it's a transfer
    # before the other half looks for it.
    order = lambda p: (p[2].transacted_on, p[0].amount_only or p[2].anonymous, not p[2].is_debit, p[2].booked_on, p[2].reference)  # noqa: E731
    for connection, account, txn in sorted(fetched, key=order):
        reference = f"{connection.source_prefix}:{txn.reference}"
        if reference in handled or txn.transacted_on < connection.since or txn.transacted_on > as_of:
            continue
        if (connection.amount_only or txn.anonymous) and txn.booked_on > as_of - timedelta(days=AMOUNT_ONLY_GRACE_DAYS):
            continue  # not yet: left unrecorded, so a later run handles it once it's due
        if txn.currency != "EUR":
            continue  # gripr's bank accounts are EUR; a foreign-currency entry would need FX first
        _handle(ctx, connection, account, txn)
        handled.add(reference)

    for connection in succeeded:
        bank_sync_repo.update_connection(db, connection, last_synced_at=_utcnow(), last_error=None)
    return result
