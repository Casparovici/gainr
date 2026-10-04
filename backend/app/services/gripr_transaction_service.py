"""Wraps gripr transaction create/update/delete so a transaction filed under a category linked
to a loan account (`GriprCategory.linked_loan_account_id`) automatically nudges that loan's
balance, and an edit or delete reverses the old effect before applying the new one instead of
leaking drift into the loan balance. See docs/adr/0003.

An expense can expect part of itself back (docs/adr/0032): at most its own amount, and only while
it is an expense.

It also keeps refunds (docs/adr/0023) consistent with the expense they point at: a linked refund
always carries its expense's category, and editing or deleting that expense carries through to
the refunds instead of leaving them pointing at something that no longer matches.

This is the one place gripr transaction writes have business logic beyond the repository's plain
insert/update/delete -- the router calls these, not `gripr_transaction_repo` directly, for
create/update/delete.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gripr_category import GriprCategoryKind
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.repositories import gripr_account_repo, gripr_category_repo, gripr_transaction_repo
from app.services import gripr_portfolio_link_service


class InvalidRefundError(ValueError):
    """A refund whose shape can't be netted against spend -- see _normalize_refund."""


@dataclass(frozen=True)
class _LoanEffect:
    account_id: int
    amount: Decimal


def _loan_effect(db: Session, category_id: int | None, type_: GriprTransactionType, amount: Decimal) -> _LoanEffect | None:
    """What this transaction's shape implies for a linked loan, if anything -- a positive
    magnitude to add to the linked account's `manual_balance`. Loan balances are stored
    negative (what's still owed), so adding a positive expense amount moves the balance toward
    zero: a repayment. Only expense transactions filed under a category with a link count."""
    if category_id is None or type_ != GriprTransactionType.EXPENSE:
        return None
    category = gripr_category_repo.get_category(db, category_id)
    if category is None or category.linked_loan_account_id is None:
        return None
    return _LoanEffect(account_id=category.linked_loan_account_id, amount=amount)


def _apply(db: Session, effect: _LoanEffect | None, sign: int) -> None:
    if effect is None:
        return
    loan = gripr_account_repo.get_account(db, effect.account_id)
    if loan is None:
        # The link pointed at an account that's since been deleted -- nothing to adjust.
        return
    loan.manual_balance = loan.manual_balance + sign * effect.amount


def _normalize_refund(db: Session, fields: dict, current: GriprTransaction | None = None) -> None:
    """Validates and fills in `fields` (in place) for the transaction's shape after this write.
    A refund linked to an expense takes that expense's category -- it's the same spending, part
    of it coming back -- and any refund has to sit under an expense category, since that's the
    spend it nets against. Anything that isn't a refund can't point at an expense."""
    type_ = fields.get("type", current.type if current else None)
    if type_ != GriprTransactionType.REFUND:
        if "refund_of_id" in fields or (current is not None and current.refund_of_id is not None):
            fields["refund_of_id"] = None
        return

    fields["counter_account_id"] = None
    refund_of_id = fields.get("refund_of_id", current.refund_of_id if current else None)
    if refund_of_id is not None:
        original = gripr_transaction_repo.get_transaction(db, refund_of_id)
        if original is None or original.type != GriprTransactionType.EXPENSE:
            raise InvalidRefundError("a refund can only point at an expense")
        if current is not None and original.id == current.id:
            raise InvalidRefundError("a transaction can't refund itself")
        fields["category_id"] = original.category_id

    ensure_refund_category(db, fields.get("category_id", current.category_id if current else None))


def ensure_refund_category(db: Session, category_id: int | None) -> None:
    """A refund nets against spend, so it has to sit under an expense category (or none yet).
    Also checked on recurring refund rules, whose occurrences go through _normalize_refund."""
    if category_id is None:
        return
    category = gripr_category_repo.get_category(db, category_id)
    if category is not None and category.kind != GriprCategoryKind.EXPENSE:
        raise InvalidRefundError("a refund belongs under an expense category")


def _sync_refunds_of(db: Session, txn: GriprTransaction) -> None:
    """Carries an expense edit through to the refunds pointing at it: a new category moves them
    along, and an expense that's no longer an expense leaves them unlinked (still real money
    that came in, just no longer attributed to anything)."""
    for refund in gripr_transaction_repo.list_refunds_of(db, txn.id):
        if txn.type == GriprTransactionType.EXPENSE:
            refund.category_id = txn.category_id
        else:
            refund.refund_of_id = None
    db.flush()


def _normalize_expected(fields: dict, current: GriprTransaction | None = None) -> None:
    """Only an expense can expect money back, never more than it cost; nothing (or zero) expected
    clears who it was expected from too."""
    type_ = fields.get("type", current.type if current else None)
    expected = fields.get("expected_back", current.expected_back if current else None)
    if type_ != GriprTransactionType.EXPENSE or expected is None or expected <= 0:
        if "expected_back" in fields or (current is not None and current.expected_back is not None):
            fields["expected_back"] = None
            fields["expected_from"] = None
        return
    amount = fields.get("amount", current.amount if current else None)
    if amount is not None and expected > amount:
        raise InvalidRefundError("can't expect back more than the expense itself")
    if "expected_from" in fields:
        fields["expected_from"] = (fields["expected_from"] or "").strip() or None


def create_transaction(db: Session, **fields) -> GriprTransaction:
    _normalize_refund(db, fields)
    _normalize_expected(fields)
    txn = gripr_transaction_repo.create_transaction(db, **fields)
    apply_effects(db, txn)
    return txn


def apply_effects(db: Session, txn: GriprTransaction) -> None:
    """The loan-balance/portfolio-mirror side effects a normal create applies immediately --
    pulled out so a transaction pre-booked ahead of its own due date (see
    gripr_recurring_service.generate_due) can skip them at creation time and have them applied
    later, exactly once, the moment it actually becomes due. A future-dated transaction hasn't
    happened yet; a loan repayment or portfolio transfer dated next week shouldn't move either
    balance today.

    Idempotent: `effects_applied` records that it ran, so applying twice never moves a balance
    twice -- and edits/deletes know whether there is anything to reverse."""
    if txn.effects_applied:
        return
    effect = _loan_effect(db, txn.category_id, txn.type, txn.amount)
    _apply(db, effect, sign=1)
    _sync_portfolio_mirror(db, txn)
    txn.effects_applied = True
    db.flush()


def update_transaction(db: Session, txn: GriprTransaction, **fields) -> GriprTransaction:
    # Captured before the repo mutates txn in place, so this is genuinely the pre-image --
    # reversing it after the fact would otherwise reverse the *new* shape against itself.
    before = _loan_effect(db, txn.category_id, txn.type, txn.amount)
    _normalize_refund(db, fields, current=txn)
    _normalize_expected(fields, current=txn)
    gripr_transaction_repo.update_transaction(db, txn, **fields)
    _sync_refunds_of(db, txn)
    if not txn.effects_applied:
        # A pre-booked occurrence edited before its date: nothing was applied, so nothing to
        # reverse -- its effects still follow, with the edited shape, once it's due.
        return txn
    after = _loan_effect(db, txn.category_id, txn.type, txn.amount)
    _apply(db, before, sign=-1)
    _apply(db, after, sign=1)
    _sync_portfolio_mirror(db, txn)
    return txn


def delete_transaction(db: Session, txn: GriprTransaction) -> None:
    if txn.effects_applied:
        effect = _loan_effect(db, txn.category_id, txn.type, txn.amount)
        _apply(db, effect, sign=-1)
    gripr_portfolio_link_service.remove_mirror(db, txn)
    # Refunds of a deleted expense stay -- the money really came in -- they just lose the link.
    for refund in gripr_transaction_repo.list_refunds_of(db, txn.id):
        refund.refund_of_id = None
    gripr_transaction_repo.delete_transaction(db, txn)
    gripr_portfolio_link_service.sync_balance(db)


def _sync_portfolio_mirror(db: Session, txn: GriprTransaction) -> None:
    """Mirrors the transfer into gainr's cash ledger, then re-reads the portfolio value back
    onto the linked account's balance -- the deposit just booked is part of that value, so the
    balance would otherwise sit one transfer behind until the next daily sync."""
    gripr_portfolio_link_service.sync_mirror(db, txn)
    gripr_portfolio_link_service.sync_balance(db)
