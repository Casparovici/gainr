from datetime import date
from decimal import Decimal

import pytest

from app.models.asset import Asset
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_transaction import GriprTransactionType
from app.models.price_history import PriceHistory
from app.models.transaction import Transaction, TransactionType
from app.repositories import gripr_transaction_repo, transaction_repo
from app.services import gripr_portfolio_link_service, gripr_transaction_service
from app.services.portfolio_service import create_portfolio, get_main_portfolio


def make_account(db, name, type_=GriprAccountType.CHECKING, mode=GriprBalanceMode.TRANSACTIONAL) -> GriprAccount:
    account = GriprAccount(name=name, type=type_, balance_mode=mode)
    db.add(account)
    db.flush()
    return account


def link(db, account, portfolio_id: int | None = None) -> None:
    portfolio_id = portfolio_id if portfolio_id is not None else get_main_portfolio(db).id
    gripr_portfolio_link_service.set_link(db, account.id, portfolio_id)
    db.flush()


def gainr_cash_rows(db) -> list[Transaction]:
    main_id = get_main_portfolio(db).id
    return [
        t for t in transaction_repo.list_all_transactions(db, main_id)
        if t.source_ref and t.source_ref.startswith("pefi_transfer:")
    ]


def test_transfer_into_the_linked_account_books_a_deposit_in_gainr(db_session):
    checking = make_account(db_session, "ING")
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("500"), account_id=checking.id, counter_account_id=beleggen.id,
    )
    db_session.commit()

    rows = gainr_cash_rows(db_session)
    assert len(rows) == 1
    assert rows[0].type == TransactionType.DEPOSIT
    assert rows[0].total_eur == Decimal("500")
    assert rows[0].date == date(2026, 3, 1)
    assert rows[0].asset_id is None  # a pure cash movement, not tied to a holding


def test_transfer_out_of_the_linked_account_books_a_withdrawal(db_session):
    checking = make_account(db_session, "ING")
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("200"), account_id=beleggen.id, counter_account_id=checking.id,
    )
    db_session.commit()

    rows = gainr_cash_rows(db_session)
    assert [r.type for r in rows] == [TransactionType.WITHDRAW]
    assert rows[0].total_eur == Decimal("200")


def test_transfers_between_other_accounts_are_not_mirrored(db_session):
    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "Spaarrekening", GriprAccountType.SAVINGS)
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("500"), account_id=checking.id, counter_account_id=savings.id,
    )
    db_session.commit()

    assert gainr_cash_rows(db_session) == []


def test_an_expense_on_the_linked_account_is_not_mirrored(db_session):
    """A fee or dividend booked straight onto the brokerage account is already in gainr's own
    ledger — mirroring it would count the same money twice."""
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.EXPENSE,
        amount=Decimal("19.08"), account_id=beleggen.id,
    )
    db_session.commit()

    assert gainr_cash_rows(db_session) == []


def test_editing_the_transfer_amount_updates_the_mirrored_deposit(db_session):
    checking = make_account(db_session, "ING")
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("500"), account_id=checking.id, counter_account_id=beleggen.id,
    )

    gripr_transaction_service.update_transaction(db_session, txn, amount=Decimal("750"), date=date(2026, 3, 4))
    db_session.commit()

    rows = gainr_cash_rows(db_session)
    assert len(rows) == 1  # updated in place, not a second row
    assert rows[0].total_eur == Decimal("750")
    assert rows[0].date == date(2026, 3, 4)


def test_retargeting_a_transfer_away_removes_the_mirror(db_session):
    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "Spaarrekening", GriprAccountType.SAVINGS)
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("500"), account_id=checking.id, counter_account_id=beleggen.id,
    )

    gripr_transaction_service.update_transaction(db_session, txn, counter_account_id=savings.id)
    db_session.commit()

    assert gainr_cash_rows(db_session) == []


def test_deleting_the_transfer_deletes_the_mirrored_deposit(db_session):
    checking = make_account(db_session, "ING")
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)
    txn = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("500"), account_id=checking.id, counter_account_id=beleggen.id,
    )

    gripr_transaction_service.delete_transaction(db_session, txn)
    db_session.commit()

    assert gainr_cash_rows(db_session) == []


def test_nothing_is_mirrored_while_no_account_is_linked(db_session):
    checking = make_account(db_session, "ING")
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("500"), account_id=checking.id, counter_account_id=beleggen.id,
    )
    db_session.commit()

    assert gainr_cash_rows(db_session) == []


def test_sync_balance_writes_the_portfolio_value_onto_the_linked_account(db_session):
    """Market movement is a balance correction, never a transaction — the account's balance
    becomes gainr's total (cash + holdings) without anything being booked in gripr."""
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)
    main_id = get_main_portfolio(db_session).id
    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    db_session.add_all([
        Transaction(portfolio_id=main_id, asset_id=None, date=date(2026, 1, 1), type=TransactionType.DEPOSIT,
                    value_eur=Decimal(1000), costs=Decimal(0), total_eur=Decimal(1000)),
        Transaction(portfolio_id=main_id, asset_id=asset.id, date=date(2026, 1, 2), type=TransactionType.BUY,
                    quantity=Decimal(10), value_eur=Decimal(250), costs=Decimal(0), total_eur=Decimal(250)),
        PriceHistory(asset_id=asset.id, date=date.today(), close_price=Decimal(30)),
    ])
    db_session.flush()

    balances = gripr_portfolio_link_service.sync_balance(db_session)
    db_session.commit()

    # 750 cash left after the buy, holding now worth 10 * 30 = 300.
    assert balances == {beleggen.id: Decimal("1050.00")}
    assert beleggen.manual_balance == Decimal("1050.00")
    assert beleggen.balance_mode == GriprBalanceMode.MANUAL
    # The whole point: the gain landed as a balance, not as a booked money movement.
    assert gripr_transaction_repo.list_transactions(db_session, account_id=beleggen.id)[0] == []


def test_sync_balance_is_a_no_op_when_nothing_is_linked(db_session):
    make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)

    assert gripr_portfolio_link_service.sync_balance(db_session) == {}


def test_a_second_account_can_link_to_a_second_portfolio(db_session):
    """The whole point of generalizing past one hardcoded link: Kids' brokerage account mirrors
    the Kids portfolio, entirely independent of Main and Beleggen."""
    checking = make_account(db_session, "ING")
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    kids_account = make_account(db_session, "Beleggingsrekening kinderen", GriprAccountType.INVESTMENT)
    kids_portfolio = create_portfolio(db_session, "Kids")
    link(db_session, beleggen)
    link(db_session, kids_account, kids_portfolio.id)

    gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 3, 1), type=GriprTransactionType.TRANSFER,
        amount=Decimal("100"), account_id=checking.id, counter_account_id=kids_account.id,
    )
    db_session.commit()

    # Only the Kids portfolio's cash ledger got the mirrored deposit -- Main's is untouched.
    assert gainr_cash_rows(db_session) == []
    kids_rows = [
        t for t in transaction_repo.list_all_transactions(db_session, kids_portfolio.id)
        if t.source_ref and t.source_ref.startswith("pefi_transfer:")
    ]
    assert len(kids_rows) == 1
    assert kids_rows[0].total_eur == Decimal("100")


def test_sync_balance_keeps_each_linked_accounts_balance_independent(db_session):
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    kids_account = make_account(db_session, "Beleggingsrekening kinderen", GriprAccountType.INVESTMENT)
    kids_portfolio = create_portfolio(db_session, "Kids")
    link(db_session, beleggen)
    link(db_session, kids_account, kids_portfolio.id)
    main_id = get_main_portfolio(db_session).id
    db_session.add_all([
        Transaction(portfolio_id=main_id, asset_id=None, date=date(2026, 1, 1), type=TransactionType.DEPOSIT,
                    value_eur=Decimal(1000), costs=Decimal(0), total_eur=Decimal(1000)),
        Transaction(portfolio_id=kids_portfolio.id, asset_id=None, date=date(2026, 1, 1), type=TransactionType.DEPOSIT,
                    value_eur=Decimal(200), costs=Decimal(0), total_eur=Decimal(200)),
    ])
    db_session.flush()

    balances = gripr_portfolio_link_service.sync_balance(db_session)
    db_session.commit()

    assert balances == {beleggen.id: Decimal("1000.00"), kids_account.id: Decimal("200.00")}


def test_linking_an_already_linked_portfolio_to_another_account_is_rejected(db_session):
    beleggen = make_account(db_session, "Beleggen", GriprAccountType.INVESTMENT)
    other = make_account(db_session, "Robeco Beleggen", GriprAccountType.INVESTMENT)
    link(db_session, beleggen)

    with pytest.raises(gripr_portfolio_link_service.PortfolioAlreadyLinkedError):
        gripr_portfolio_link_service.set_link(db_session, other.id, get_main_portfolio(db_session).id)
