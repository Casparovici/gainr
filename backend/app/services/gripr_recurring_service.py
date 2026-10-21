from dataclasses import dataclass
from datetime import date as date_, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.repositories import (
    bank_sync_repo,
    gripr_account_repo,
    gripr_depreciation_repo,
    gripr_recurring_repo,
    gripr_transaction_repo,
)
from app.services import gripr_depreciation_service, gripr_transaction_service
from app.services.gripr_period_service import period_bounds

_UNIT = {
    GriprRecurrenceFrequency.WEEKLY: "weeks",
    GriprRecurrenceFrequency.MONTHLY: "months",
    GriprRecurrenceFrequency.YEARLY: "years",
}


def advance(frequency: GriprRecurrenceFrequency, from_date: date_, interval: int = 1) -> date_:
    return from_date + relativedelta(**{_UNIT[frequency]: interval})


# Most occurrences one rule may catch up on in a single pass. Nothing is dropped: next_due_date
# stays where the loop stopped, so the remainder is booked on the next call. This only bounds how
# much work one page load can trigger -- a rule anchored at a mistyped year (2015 for 2025) would
# otherwise book a decade of weekly transactions, and a loan-linked one a decade of balance
# adjustments, inside a single request. 120 clears any realistic catch-up (10 years monthly).
MAX_CATCHUP_PER_RULE = 120

# How far ahead of its own due date a rule's next occurrence gets pre-booked. Per-rule, not a
# global "next 2 days" query -- with many rules on staggered schedules, "pre-book whatever's
# due within the next 2 days" and "pre-book each rule's own next occurrence, but only once it's
# within 2 days out" land on the same set, since a rule further out than that simply hasn't
# reached its own pre-book window yet and gets picked up on a later call once it has.
PREBOOK_HORIZON_DAYS = 2

# How far from its due date a bank entry still counts as a rule's occurrence (see
# bank_sync_service), and so how long a bank-fed rule waits for one before moving on to its next
# occurrence regardless -- a charge that never came (a skipped month) shouldn't leave the rule
# stuck "due" forever.
BANK_FULFIL_DAYS = 5


def _source_ref(rule: GriprRecurringTransaction, occurrence: date_) -> str:
    return f"pefi_recurring:{rule.id}:{occurrence.isoformat()}"


def _book_due_occurrence(db: Session, rule: GriprRecurringTransaction, occurrence: date_) -> GriprTransaction | None:
    """Books `occurrence` for `rule`, which has actually arrived (occurrence <= as_of) -- with
    the loan-balance/portfolio-mirror side effects a normal transaction gets. If a previous call
    already pre-booked this exact occurrence ahead of schedule (see _prebook_next_occurrence),
    those side effects were deliberately skipped back then, so this applies them now instead of
    creating a duplicate row -- exactly once, since the next call won't find this source_ref
    "not yet applied" again. Returns the transaction only when this call is the one that
    inserted the row, matching generate_due's "what did I just create" return contract."""
    source_ref = _source_ref(rule, occurrence)
    existing = gripr_transaction_repo.get_by_source_ref(db, source_ref)
    if existing is not None:
        gripr_transaction_service.apply_effects(db, existing)
        return None
    return gripr_transaction_service.create_transaction(
        db,
        date=occurrence,
        type=rule.type,
        amount=rule.amount,
        account_id=rule.account_id,
        counter_account_id=rule.counter_account_id,
        category_id=rule.category_id,
        notes=rule.notes,
        source_ref=source_ref,
        depreciations=gripr_depreciation_service.for_rule(db, rule.id),
    )


def _prebook_next_occurrence(db: Session, rule: GriprRecurringTransaction) -> GriprTransaction | None:
    """Books `rule`'s next occurrence ahead of its own due date, as a plain ledger row -- no
    loan/portfolio side effects, since it hasn't actually happened yet (_book_due_occurrence
    applies them later, once it has). A future-dated row doesn't count toward any balance,
    budget, or overview total either (gripr_transaction_repo's `date <= today` cutoff), so this
    is safe to do early: exactly as if the user had entered it by hand ahead of time. Returns
    None, not just skips creating, when it's already there from an earlier call."""
    source_ref = _source_ref(rule, rule.next_due_date)
    if gripr_transaction_repo.exists_by_source_ref(db, source_ref):
        return None
    txn = gripr_transaction_repo.create_transaction(
        db,
        date=rule.next_due_date,
        type=rule.type,
        amount=rule.amount,
        account_id=rule.account_id,
        counter_account_id=rule.counter_account_id,
        category_id=rule.category_id,
        notes=rule.notes,
        source_ref=source_ref,
    )
    # Carried now, applied when it is due (apply_effects), like the other side effects.
    gripr_depreciation_service.attach(db, txn, gripr_depreciation_service.for_rule(db, rule.id))
    return txn


def generate_due(db: Session, as_of: date_ | None = None) -> list[GriprTransaction]:
    """Books a real ledger transaction for every occurrence a rule has reached but hasn't
    materialized yet, looping forward one period at a time so a rule nobody's checked on in a
    while (the app has no live scheduler — this runs opportunistically whenever the recurring
    list or accounts are read) catches up on every missed occurrence, not just the latest one.
    `source_ref` makes each occurrence idempotent the same way the CSV importer's rows are.

    Once a rule is fully caught up, also pre-books its *next* occurrence once it's within
    PREBOOK_HORIZON_DAYS of its own due date -- so it shows up, editable, in the Transactions
    list a couple of days before it actually happens (see docs/adr/0020) -- but leaves
    `next_due_date` pointing at it rather than past it, so "next due" always names the same
    date as that pre-booked row instead of the one after. Skipped while a rule is still
    mid-catch-up (next_due_date still <= as_of after hitting MAX_CATCHUP_PER_RULE) -- there's
    nothing "ahead of schedule" about an occurrence that's actually overdue.
    """
    as_of = as_of or date_.today()
    prebook_by = as_of + timedelta(days=PREBOOK_HORIZON_DAYS)
    bank_fed = bank_sync_repo.bank_fed_account_ids(db)
    recognisable = bank_fed | bank_sync_repo.rule_target_account_ids(db) if bank_fed else set()
    homes = gripr_account_repo.pot_parents(db) if bank_fed else {}
    created: list[GriprTransaction] = []
    for rule in gripr_recurring_repo.list_recurring(db, include_inactive=False):
        if is_bank_fed(rule, bank_fed, recognisable, homes):
            _leave_to_bank(db, rule, as_of)
            continue
        booked = 0
        while (
            booked < MAX_CATCHUP_PER_RULE
            and rule.next_due_date <= as_of
            and (rule.end_date is None or rule.next_due_date <= rule.end_date)
        ):
            txn = _book_due_occurrence(db, rule, rule.next_due_date)
            if txn is not None:
                created.append(txn)
            booked += 1
            rule.next_due_date = advance(rule.frequency, rule.next_due_date, rule.interval)
        # Ran past its own end date — nothing left to ever generate.
        if rule.end_date is not None and rule.next_due_date > rule.end_date:
            rule.is_active = False
            continue
        if as_of < rule.next_due_date <= prebook_by:
            txn = _prebook_next_occurrence(db, rule)
            if txn is not None:
                created.append(txn)
    db.flush()
    return created


def is_bank_fed(
    rule: GriprRecurringTransaction, bank_fed: set[int], recognisable: set[int], homes: dict[int, int] | None = None
) -> bool:
    """Whether a bank's own entry will stand in for this rule's occurrences: an expense or income
    on a bank-fed account (or on a virtual pot inside one -- `homes` maps a pot to its account), or
    a transfer touching one whose other side the bank sync can recognise too (another fed account,
    or one a counterparty rule points at). Money moving between an account and its own pot, or
    into a pot nothing at the bank corresponds to, never shows up in bank data, so that rule keeps
    booking its own rows."""
    homes = homes or {}

    def home(account_id: int | None) -> int | None:
        return homes.get(account_id, account_id) if account_id is not None else None

    if rule.type != GriprTransactionType.TRANSFER:
        return home(rule.account_id) in bank_fed
    sides = (home(rule.account_id), home(rule.counter_account_id))
    if sides[0] == sides[1]:
        return False  # between an account and its own pot: internal, the bank never sees it
    return any(side in bank_fed for side in sides) and all(side in recognisable for side in sides)


def _leave_to_bank(db: Session, rule: GriprRecurringTransaction, as_of: date_) -> None:
    """A rule on an account ING feeds books nothing itself: the bank's own entry is the real
    occurrence, and bank_sync_service files it under the rule (its category, its schedule moved
    on) when one arrives near the due date. Booking the rule's row as well would count the same
    payment twice -- with the rule's estimated amount, not what was actually paid. All this does
    is keep the rule tidy: drop an occurrence pre-booked before the account was bank-fed, and
    move past occurrences whose window has closed without a bank entry. See docs/adr/0029."""
    _remove_unbooked_future_occurrence(db, rule, as_of)
    steps = 0
    while (
        steps < MAX_CATCHUP_PER_RULE
        and rule.next_due_date < as_of - timedelta(days=BANK_FULFIL_DAYS)
        and (rule.end_date is None or rule.next_due_date <= rule.end_date)
    ):
        rule.next_due_date = advance(rule.frequency, rule.next_due_date, rule.interval)
        steps += 1
    if rule.end_date is not None and rule.next_due_date > rule.end_date:
        rule.is_active = False


def update_recurring(
    db: Session, rule: GriprRecurringTransaction, as_of: date_ | None = None, **fields
) -> GriprRecurringTransaction:
    as_of = as_of or date_.today()
    # Redefining the schedule's anchor restarts the countdown from there, same as creating a
    # new rule would — otherwise a start_date moved into the future would still fire on the old
    # next_due_date first.
    if "start_date" in fields and fields["start_date"] is not None:
        fields["next_due_date"] = fields["start_date"]
    elif fields.get("is_active") is True and not rule.is_active:
        # Resuming skips the pause rather than backfilling it: pausing a rule means those
        # occurrences didn't happen (a paused subscription doesn't bill you), so booking them
        # all on resume would invent money movements. Occurrences booked before the pause stay.
        fields["next_due_date"] = _next_occurrence_after(rule, as_of)
    elif fields.get("is_active") is False and rule.is_active:
        _remove_unbooked_future_occurrence(db, rule, as_of)
    return gripr_recurring_repo.update_recurring(db, rule, **fields)


def _remove_unbooked_future_occurrence(db: Session, rule: GriprRecurringTransaction, as_of: date_) -> None:
    """A pre-booked occurrence (see generate_due) ahead of its own due date represents a charge
    that hasn't happened yet -- pausing means it won't, so it's removed rather than left sitting
    in the ledger as something that will never occur. An occurrence whose date has already
    arrived is real money that already moved and stays untouched, same as any other pause."""
    txn = gripr_transaction_repo.get_by_source_ref(db, _source_ref(rule, rule.next_due_date))
    if txn is not None and txn.date > as_of:
        gripr_transaction_repo.delete_transaction(db, txn)


def _next_occurrence_after(rule: GriprRecurringTransaction, as_of: date_) -> date_:
    """Walks the rule's own rhythm forward past `as_of` instead of restarting from it, so a rule
    anchored to the 14th still lands on the 14th after being resumed."""
    next_due = rule.next_due_date
    while next_due <= as_of:
        next_due = advance(rule.frequency, next_due, rule.interval)
    return next_due


@dataclass(frozen=True)
class PlannedOccurrence:
    rule: GriprRecurringTransaction
    date: date_


def planned_occurrences(db: Session, as_of: date_, until: date_) -> list[PlannedOccurrence]:
    """Every occurrence an active rule will reach after `as_of` and up to `until`, that isn't in
    the ledger yet -- a projection only, nothing is booked. generate_due pre-books a rule's next
    occurrence just PREBOOK_HORIZON_DAYS out, so on its own the "what's still coming this period"
    question would only ever see the next two days; this fills in the rest. An occurrence that
    *is* already booked (pre-booked, or the user entered it) is left out, since it already shows
    up as a real future-dated transaction. Sorted by date, then name."""
    planned: list[PlannedOccurrence] = []
    for rule in gripr_recurring_repo.list_recurring(db, include_inactive=False):
        occurrence = rule.next_due_date
        steps = 0
        while (
            steps < MAX_CATCHUP_PER_RULE
            and occurrence <= until
            and (rule.end_date is None or occurrence <= rule.end_date)
        ):
            if occurrence > as_of and not gripr_transaction_repo.exists_by_source_ref(db, _source_ref(rule, occurrence)):
                planned.append(PlannedOccurrence(rule=rule, date=occurrence))
            occurrence = advance(rule.frequency, occurrence, rule.interval)
            steps += 1
    return sorted(planned, key=lambda p: (p.date, p.rule.name))


def planned_until_period_end(db: Session, start_day: int, as_of: date_ | None = None) -> tuple[date_, list[PlannedOccurrence]]:
    """planned_occurrences through the end of the period `as_of` falls in (gripr's configurable
    period, see gripr_period_service) -- the "still to come this period" view."""
    as_of = as_of or date_.today()
    until = period_bounds(as_of, start_day)[1]
    return until, planned_occurrences(db, as_of, until)


def delete_rule(db: Session, rule: GriprRecurringTransaction) -> None:
    """The rule and its depreciation plan (ADR 0034). Transactions it already booked stay."""
    gripr_depreciation_repo.delete_for_rule(db, rule.id)
    gripr_recurring_repo.delete_recurring(db, rule)
