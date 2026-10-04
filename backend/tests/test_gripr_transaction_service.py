from datetime import date
from decimal import Decimal

from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_transaction_repo
from app.services import gripr_recurring_service, gripr_transaction_service


def make_loan(db, name="Studieschuld", balance="-14155.03") -> GriprAccount:
    loan = GriprAccount(
        name=name, type=GriprAccountType.LOAN, balance_mode=GriprBalanceMode.MANUAL,
        manual_balance=Decimal(balance),
    )
    db.add(loan)
    db.flush()
    return loan


def make_checking(db, name="ING") -> GriprAccount:
    account = GriprAccount(name=name, type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db.add(account)
    db.flush()
    return account


def make_category(db, name, linked_loan_account_id=None, kind=GriprCategoryKind.EXPENSE) -> GriprCategory:
    category = GriprCategory(name=name, kind=kind, linked_loan_account_id=linked_loan_account_id)
    db.add(category)
    db.flush()
    return category


def test_creating_an_expense_against_a_linked_category_moves_the_loan_balance(db_session):
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    category = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("155.03"), account_id=checking.id, category_id=category.id,
    )
    db_session.commit()

    assert loan.manual_balance == Decimal("-14000.00")


def test_unlinked_category_never_touches_any_loan_balance(db_session):
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    category = make_category(db_session, "Boodschappen")

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("50"), account_id=checking.id, category_id=category.id,
    )
    db_session.commit()

    assert loan.manual_balance == Decimal("-14155.03")


def test_income_or_transfer_against_a_linked_category_is_ignored(db_session):
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    income_category = make_category(db_session, "Salaris", linked_loan_account_id=loan.id, kind=GriprCategoryKind.INCOME)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.INCOME,
        amount=Decimal("2000"), account_id=checking.id, category_id=income_category.id,
    )
    db_session.commit()

    assert loan.manual_balance == Decimal("-14155.03")


def test_updating_the_amount_adjusts_by_the_delta_not_the_full_new_amount(db_session):
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    category = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("100"), account_id=checking.id, category_id=category.id,
    )
    db_session.commit()
    assert loan.manual_balance == Decimal("-14055.03")

    gripr_transaction_service.update_transaction(db_session, txn, amount=Decimal("150"))
    db_session.commit()

    # Reverse the old +100, then apply the new +150, against the original -14155.03 baseline —
    # not -14155.03 - 150 (which would double-count the original 100).
    assert loan.manual_balance == Decimal("-14005.03")


def test_moving_a_transaction_from_one_linked_category_to_another_reverses_and_reapplies(db_session):
    loan_a = make_loan(db_session, "Studieschuld", "-10000")
    loan_b = make_loan(db_session, "Hypotheek", "-200000")
    checking = make_checking(db_session)
    category_a = make_category(db_session, "Studieschuld", linked_loan_account_id=loan_a.id)
    category_b = make_category(db_session, "Hypotheek", linked_loan_account_id=loan_b.id)
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("500"), account_id=checking.id, category_id=category_a.id,
    )
    db_session.commit()
    assert loan_a.manual_balance == Decimal("-9500")

    gripr_transaction_service.update_transaction(db_session, txn, category_id=category_b.id)
    db_session.commit()

    assert loan_a.manual_balance == Decimal("-10000")  # reversed
    assert loan_b.manual_balance == Decimal("-199500")  # applied


def test_unlinking_a_transactions_category_stops_the_adjustment(db_session):
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    linked = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)
    unlinked = make_category(db_session, "Boodschappen")
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("100"), account_id=checking.id, category_id=linked.id,
    )
    db_session.commit()
    assert loan.manual_balance == Decimal("-14055.03")

    gripr_transaction_service.update_transaction(db_session, txn, category_id=unlinked.id)
    db_session.commit()

    assert loan.manual_balance == Decimal("-14155.03")


def test_deleting_a_linked_transaction_reverses_its_effect(db_session):
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    category = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("100"), account_id=checking.id, category_id=category.id,
    )
    db_session.commit()
    assert loan.manual_balance == Decimal("-14055.03")

    gripr_transaction_service.delete_transaction(db_session, txn)
    db_session.commit()

    assert loan.manual_balance == Decimal("-14155.03")


def test_create_update_update_delete_round_trips_the_loan_balance(db_session):
    """The strongest guarantee this kind of two-sided mutation needs: a full lifecycle of
    edits nets back to exactly where the loan balance started."""
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    category = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)
    original = loan.manual_balance

    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("100"), account_id=checking.id, category_id=category.id,
    )
    gripr_transaction_service.update_transaction(db_session, txn, amount=Decimal("237.50"))
    gripr_transaction_service.update_transaction(db_session, txn, amount=Decimal("42"))
    gripr_transaction_service.delete_transaction(db_session, txn)
    db_session.commit()

    assert loan.manual_balance == original


def test_apply_effects_moves_the_loan_balance_for_a_row_created_without_it(db_session):
    """The building block gripr_recurring_service leans on to defer a pre-booked future
    occurrence's loan effect until it's actually due -- a plain repo-level insert (bypassing
    create_transaction) never touches the loan balance on its own; apply_effects is what does,
    called separately once the occurrence is due."""
    from app.repositories import gripr_transaction_repo

    loan = make_loan(db_session)
    checking = make_checking(db_session)
    category = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)

    txn = gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 6, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("100"), account_id=checking.id, category_id=category.id,
    )
    db_session.commit()
    assert loan.manual_balance == Decimal("-14155.03")  # untouched by the plain insert

    gripr_transaction_service.apply_effects(db_session, txn)
    db_session.commit()

    assert loan.manual_balance == Decimal("-14055.03")


def test_editing_a_transfer_into_an_expense_clears_its_counter_account(db_session):
    """An explicit None has to land, not be skipped as "nothing to do": a stranded
    counter_account_id keeps the transaction showing up under that account, since
    list_transactions matches either side of a transfer."""
    checking = make_checking(db_session)
    savings = make_checking(db_session, name="Spaarrekening")
    category = make_category(db_session, "Boodschappen")

    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 1, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("250"), account_id=checking.id, counter_account_id=savings.id,
    )
    gripr_transaction_service.update_transaction(
        db_session, txn, type=GriprTransactionType.EXPENSE,
        category_id=category.id, counter_account_id=None,
    )
    db_session.commit()

    assert txn.counter_account_id is None
    assert txn.category_id == category.id


# -- pre-booked occurrences: effects deferred, so nothing to reverse (docs/adr/0020) ----------

def _studieschuld_rule(db, loan, checking, due=date(2026, 10, 25)) -> GriprRecurringTransaction:
    category = make_category(db, "Studieschuld", linked_loan_account_id=loan.id)
    rule = GriprRecurringTransaction(
        name="Studieschuld", type=GriprTransactionType.EXPENSE, amount=Decimal("154.99"), account_id=checking.id,
        category_id=category.id, frequency=GriprRecurrenceFrequency.MONTHLY, interval=1, start_date=due, next_due_date=due,
    )
    db.add(rule)
    db.flush()
    return rule


def test_deleting_a_pre_booked_occurrence_leaves_the_loan_alone(db_session):
    # What happened on 26 Sep 2026: the pre-booked 25 Oct repayment was deleted, and €154.99 went
    # back onto the loan that had never come off for it -- undoing the real 25 Sep repayment.
    loan = make_loan(db_session, balance="-14000.04")
    rule = _studieschuld_rule(db_session, loan, make_checking(db_session))
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 23))  # pre-books 25 Oct
    pre_booked = gripr_transaction_repo.get_by_source_ref(db_session, f"pefi_recurring:{rule.id}:2026-10-25")
    assert pre_booked is not None and pre_booked.effects_applied is False

    gripr_transaction_service.delete_transaction(db_session, pre_booked)

    assert loan.manual_balance == Decimal("-14000.04")


def test_editing_a_pre_booked_occurrence_defers_its_effect_until_due_once(db_session):
    loan = make_loan(db_session, balance="-14000.04")
    rule = _studieschuld_rule(db_session, loan, make_checking(db_session))
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 23))
    pre_booked = gripr_transaction_repo.get_by_source_ref(db_session, f"pefi_recurring:{rule.id}:2026-10-25")

    gripr_transaction_service.update_transaction(db_session, pre_booked, amount=Decimal("160.00"))
    assert loan.manual_balance == Decimal("-14000.04")  # still not due

    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 25))
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 26))
    assert loan.manual_balance == Decimal("-13840.04")  # the edited amount, applied exactly once
    assert pre_booked.effects_applied is True


def test_apply_effects_is_idempotent_and_deleting_afterwards_reverses_once(db_session):
    loan = make_loan(db_session)
    checking = make_checking(db_session)
    category = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 9, 25), type=GriprTransactionType.EXPENSE, amount=Decimal("154.99"),
        account_id=checking.id, category_id=category.id,
    )

    gripr_transaction_service.apply_effects(db_session, txn)  # a second call must not pay twice
    assert loan.manual_balance == Decimal("-14000.04")

    gripr_transaction_service.delete_transaction(db_session, txn)
    assert loan.manual_balance == Decimal("-14155.03")
