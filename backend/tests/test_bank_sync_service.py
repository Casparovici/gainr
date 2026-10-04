from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import config
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.models.bank_sync import BankConnection
from app.repositories import bank_sync_repo, gripr_transaction_repo
from app.services import bank_sync_service, gripr_recurring_service, gripr_transaction_service
from app.services.enablebanking_provider import BankAccount, BankSession, BankTransaction, EnableBankingSessionError
from app.services.trading212_provider import CashEntry, Trading212AuthError

T = GriprTransactionType
SINCE = date(2026, 10, 3)
ING = "NL11INGB0001234567"
KID = "NL22INGB0007654321"
TR = "NL33TRBK0001112223"
ADYEN = "NL04ADYB2017400157"
TR_CASH = "NL33TRBK0001112223"  # the same account as TR, once Trade Republic itself is synced


class FakeProvider:
    configured = True

    def __init__(self):
        self.transactions: dict[str, list[BankTransaction]] = {}
        self.date_froms: list[date] = []
        self.deleted: list[str] = []
        self.started: list[dict] = []
        self.session: BankSession | None = None
        self.raise_session = False

    def get_transactions(self, session_id, account_uid, iban, date_from):
        if self.raise_session:
            raise EnableBankingSessionError("session is EXPIRED")
        self.date_froms.append(date_from)
        return list(self.transactions.get(account_uid, []))

    maximum_seconds: int | None = 15552000  # ING's 180 days

    def maximum_consent_seconds(self, aspsp_name, country):
        return self.maximum_seconds

    def start_authorization(self, **kwargs):
        self.started.append(kwargs)
        return "https://tilisy.enablebanking.com/ais/start?sessionid=abc"

    def create_session(self, code):
        return self.session

    def delete_session(self, session_id):
        self.deleted.append(session_id)


_counter = 0


def bank(amount: str, day: date, *, out: bool = True, name: str = "", iban: str | None = None, description: str = "", raw: str = "", ref: str | None = None) -> BankTransaction:
    global _counter
    _counter += 1
    return BankTransaction(
        reference=ref or f"ref{_counter:06d}",
        amount=Decimal(amount),
        currency="EUR",
        is_debit=out,
        booked_on=day,
        transacted_on=day,
        counterparty_name=name,
        counterparty_iban=iban,
        description=description,
        method="Incasso",
        raw_text=raw or description,
    )


@pytest.fixture()
def provider():
    return FakeProvider()


@pytest.fixture()
def accounts(db_session):
    def make(name, type_=GriprAccountType.CHECKING):
        account = GriprAccount(name=name, type=type_, balance_mode=GriprBalanceMode.TRANSACTIONAL)
        db_session.add(account)
        return account

    made = {
        "ing": make("ING"),
        "kid": make("Rekening Sam"),
        "spaar_kid": make("Spaarrekening Sam", GriprAccountType.SAVINGS),
        "tr": make("Trade Republic", GriprAccountType.SAVINGS),
        "t212": make("T212 Debit"),
    }
    db_session.flush()
    return made


def _connection(db_session, name, prefix, **fields) -> BankConnection:
    connection = BankConnection(aspsp_name=name, aspsp_country="NL", source_prefix=prefix, **fields)
    db_session.add(connection)
    db_session.flush()
    return connection


def _live(**fields) -> dict:
    return dict(enabled=True, since=SINCE, session_id="sess-1", valid_until=datetime.now() + timedelta(days=100), **fields)


@pytest.fixture()
def ing(db_session) -> BankConnection:
    return _connection(db_session, "ING", "ing", **_live())


@pytest.fixture()
def connected(db_session, accounts, ing):
    """ING and Sam's account synced, a live consent, sync on since 3 Oct."""
    bank_sync_repo.upsert_account(db_session, ING, connection_id=ing.id, eb_uid="uid-ing", gripr_account_id=accounts["ing"].id)
    bank_sync_repo.upsert_account(db_session, KID, connection_id=ing.id, eb_uid="uid-kid", gripr_account_id=accounts["kid"].id)
    return accounts


@pytest.fixture()
def trade_republic(db_session, connected):
    """Trade Republic synced too, into the gripr Trade Republic account, from 10 Oct -- sending
    amounts only, as it does through Enable Banking."""
    tr = _connection(db_session, "Trade Republic", "tr", amount_only=True, **{**_live(), "since": date(2026, 10, 10), "session_id": "sess-tr"})
    bank_sync_repo.upsert_account(db_session, TR_CASH, connection_id=tr.id, eb_uid="uid-tr", gripr_account_id=connected["tr"].id)
    return tr


def all_rows(db_session) -> list[GriprTransaction]:
    return list(db_session.query(GriprTransaction).order_by(GriprTransaction.id))


def test_books_an_uncategorised_expense_and_income_with_the_bank_details_in_the_notes(db_session, provider, connected):
    provider.transactions["uid-ing"] = [
        bank("12.99", date(2026, 10, 4), name="Spotify", iban="NL65ADYB2006011162", description="Premium oktober"),
        bank("300.00", date(2026, 10, 5), out=False, name="Sociale Verzekeringsbank", description="KINDERBIJSLAG"),
    ]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), scheduled=True)

    assert (result.booked, result.matched, result.fulfilled) == (2, 0, 0)
    expense, income = all_rows(db_session)
    assert (expense.type, expense.amount, expense.date, expense.category_id) == (T.EXPENSE, Decimal("12.99"), date(2026, 10, 4), None)
    assert expense.account_id == connected["ing"].id
    assert expense.notes == "Spotify — Premium oktober"
    assert expense.source_ref.startswith("ing:")
    assert (income.type, income.amount) == (T.INCOME, Decimal("300.00"))


def test_running_again_books_nothing_twice(db_session, provider, connected):
    provider.transactions["uid-ing"] = [bank("12.99", date(2026, 10, 4), name="Spotify")]
    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), scheduled=True)

    again = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 7), scheduled=True)

    assert again.booked == 0
    assert len(all_rows(db_session)) == 1


def test_switched_off_does_nothing(db_session, provider, connected, ing):
    bank_sync_repo.update_connection(db_session, ing, enabled=False)
    provider.transactions["uid-ing"] = [bank("12.99", date(2026, 10, 4))]

    assert bank_sync_service.sync(db_session, provider, scheduled=True) == bank_sync_service.SyncResult()
    assert provider.date_froms == []


def test_a_start_date_still_to_come_fetches_nothing(db_session, provider, connected):
    result = bank_sync_service.sync(db_session, provider, as_of=SINCE - timedelta(days=1), scheduled=True)

    assert result == bank_sync_service.SyncResult()
    assert provider.date_froms == []


def test_an_expired_consent_is_reported_not_fetched(db_session, provider, connected, ing):
    bank_sync_repo.update_connection(db_session, ing, valid_until=bank_sync_service._utcnow() - timedelta(minutes=1))

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), scheduled=True)

    assert result.problems == {"ING": "not connected"}
    assert provider.date_froms == []


def test_a_revoked_consent_is_cleared_so_the_app_asks_to_reconnect(db_session, provider, connected, ing):
    provider.raise_session = True

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), scheduled=True)

    assert "ING" in result.problems
    assert ing.session_id is None
    assert ing.last_error
    assert ing.last_synced_at is None


def test_entries_before_since_are_left_alone_and_later_runs_reread_a_week(db_session, provider, connected, ing):
    provider.transactions["uid-ing"] = [bank("5.00", date(2026, 10, 2)), bank("6.00", date(2026, 10, 3))]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 3), scheduled=True)

    assert [r.amount for r in all_rows(db_session)] == [Decimal("6.00")]
    assert provider.date_froms[0] == SINCE
    bank_sync_repo.update_connection(db_session, ing, last_synced_at=datetime(2026, 10, 20, 6, 0))
    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 20), scheduled=True)
    assert provider.date_froms[-1] == date(2026, 10, 13)


def test_a_hand_entered_row_is_claimed_instead_of_booked_again(db_session, provider, connected):
    ing = connected["ing"].id
    hand = gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 3), type=T.EXPENSE, amount=Decimal("30.00"), account_id=ing
    )
    provider.transactions["uid-ing"] = [
        bank("30.00", date(2026, 10, 5), name="Tikkie"),
        bank("30.00", date(2026, 10, 6), name="Tikkie"),  # a second, real payment of the same amount
    ]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 7), scheduled=True)

    assert (result.matched, result.booked) == (1, 1)
    assert len(all_rows(db_session)) == 2
    assert hand.source_ref is None  # a hand-entered row is claimed, not rewritten


def test_a_transfer_entered_by_hand_matches_from_either_side(db_session, provider, connected):
    ing, tr = connected["ing"].id, connected["tr"].id
    gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 3), type=T.TRANSFER, amount=Decimal("1200.00"), account_id=tr, counter_account_id=ing
    )
    provider.transactions["uid-ing"] = [bank("1200.00", date(2026, 10, 3), out=False, iban=TR)]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 4), scheduled=True)

    assert result.matched == 1
    assert len(all_rows(db_session)) == 1


def test_a_picnic_order_the_picnic_sync_booked_is_recognised(db_session, provider, connected):
    gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 4), type=T.EXPENSE, amount=Decimal("78.71"), account_id=connected["ing"].id,
        source_ref="picnic_order:abc",
    )
    provider.transactions["uid-ing"] = [bank("78.71", date(2026, 10, 5), name="PICNIC BY BUCKAROO")]

    assert bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), scheduled=True).matched == 1


def test_counterparty_rules_book_transfers_to_and_from_own_accounts(db_session, provider, connected):
    ing, tr = connected["ing"].id, connected["tr"].id
    bank_sync_repo.create_rule(db_session, iban=TR, gripr_account_id=tr)
    provider.transactions["uid-ing"] = [
        bank("500.00", date(2026, 10, 4), name="Jan Jansen", iban=TR),
        bank("750.00", date(2026, 10, 5), out=False, name="Jan Jansen", iban=TR),
    ]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), scheduled=True)

    out, back = all_rows(db_session)
    assert (out.type, out.account_id, out.counter_account_id) == (T.TRANSFER, ing, tr)
    assert (back.type, back.account_id, back.counter_account_id) == (T.TRANSFER, tr, ing)


def test_a_rule_on_a_shared_processor_iban_needs_its_text_too(db_session, provider, connected):
    bank_sync_repo.create_rule(db_session, iban=ADYEN, text_contains="Trading 212", gripr_account_id=connected["t212"].id)
    provider.transactions["uid-ing"] = [
        bank("500.00", date(2026, 10, 4), name="Trading 212", iban=ADYEN),
        bank("17.93", date(2026, 10, 4), name="HEMA", iban=ADYEN),
    ]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), scheduled=True)

    t212, hema = sorted(all_rows(db_session), key=lambda r: -r.amount)
    assert (t212.type, t212.counter_account_id) == (T.TRANSFER, connected["t212"].id)
    assert (hema.type, hema.counter_account_id) == (T.EXPENSE, None)


def test_a_savings_number_typed_with_spaces_and_dashes_finds_the_transfer(db_session, provider, connected):
    bank_sync_repo.create_rule(db_session, text_contains="B 145-58977", gripr_account_id=connected["spaar_kid"].id)
    provider.transactions["uid-kid"] = [
        bank("10.00", date(2026, 10, 4), raw="Naar Oranje spaarrekening B14558977 Valutadatum: 04-10-2026",
             description="Naar Oranje spaarrekening B14558977"),
    ]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), scheduled=True)

    (row,) = all_rows(db_session)
    assert (row.type, row.account_id, row.counter_account_id) == (T.TRANSFER, connected["kid"].id, connected["spaar_kid"].id)


def test_a_transfer_between_two_synced_accounts_is_booked_once(db_session, provider, connected):
    provider.transactions["uid-ing"] = [bank("10.00", date(2026, 10, 4), name="Sam", iban=KID)]
    provider.transactions["uid-kid"] = [bank("10.00", date(2026, 10, 4), out=False, name="Hr J Jansen", iban=ING)]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), scheduled=True)

    assert (result.booked, result.counterparts) == (1, 1)
    (row,) = all_rows(db_session)
    assert (row.type, row.account_id, row.counter_account_id) == (T.TRANSFER, connected["ing"].id, connected["kid"].id)


def _rule(db_session, name, type_, amount, account_id, due, *, category_id=None, counter_account_id=None):
    rule = GriprRecurringTransaction(
        name=name, type=type_, amount=Decimal(amount), account_id=account_id, counter_account_id=counter_account_id,
        category_id=category_id, frequency=GriprRecurrenceFrequency.MONTHLY, interval=1, start_date=due, next_due_date=due,
    )
    db_session.add(rule)
    db_session.flush()
    return rule


def test_a_bank_entry_fulfils_its_recurring_rule_with_the_real_amount(db_session, provider, connected):
    salary = GriprCategory(name="Salaris", kind=GriprCategoryKind.INCOME)
    db_session.add(salary)
    db_session.flush()
    rule = _rule(db_session, "Salaris", T.INCOME, "3000.00", connected["ing"].id, date(2026, 10, 25), category_id=salary.id)
    provider.transactions["uid-ing"] = [bank("3150.00", date(2026, 10, 24), out=False, name="ABN AMRO BANK")]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 26), scheduled=True)

    assert result.fulfilled == 1
    (row,) = all_rows(db_session)
    assert (row.type, row.amount, row.category_id) == (T.INCOME, Decimal("3150.00"), salary.id)
    assert rule.next_due_date == date(2026, 11, 25)


def test_the_rule_named_in_the_bank_entry_wins_over_a_closer_one(db_session, provider, connected):
    ing = connected["ing"].id
    compassion = _rule(db_session, "Compassion", T.EXPENSE, "10.00", ing, date(2026, 10, 25))
    mind = _rule(db_session, "Stichting Mind", T.EXPENSE, "10.00", ing, date(2026, 10, 29))
    provider.transactions["uid-ing"] = [bank("10.00", date(2026, 10, 26), name="STICHTING MIND")]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 27), scheduled=True)

    assert mind.next_due_date == date(2026, 11, 29)
    assert compassion.next_due_date == date(2026, 10, 25)


def test_an_amount_far_off_the_rule_is_booked_on_its_own(db_session, provider, connected):
    rule = _rule(db_session, "Zorgverzekering", T.EXPENSE, "200.00", connected["ing"].id, date(2026, 10, 28))
    provider.transactions["uid-ing"] = [bank("100.00", date(2026, 10, 28), name="Zorgverzekeraar N.V.")]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 29), scheduled=True)

    assert (result.fulfilled, result.booked) == (0, 1)
    assert rule.next_due_date == date(2026, 10, 28)


def test_fulfilling_a_loan_linked_rule_moves_the_loan_balance(db_session, provider, connected):
    loan = GriprAccount(name="Hypotheek", type=GriprAccountType.LOAN, balance_mode=GriprBalanceMode.MANUAL, manual_balance=Decimal("-200000"))
    db_session.add(loan)
    db_session.flush()
    mortgage = GriprCategory(name="Hypotheek", kind=GriprCategoryKind.EXPENSE, linked_loan_account_id=loan.id)
    db_session.add(mortgage)
    db_session.flush()
    _rule(db_session, "Hypotheek", T.EXPENSE, "1500.00", connected["ing"].id, date(2026, 11, 1), category_id=mortgage.id)
    provider.transactions["uid-ing"] = [bank("1500.00", date(2026, 11, 1), name="ING Bank N.V. hypotheken incasso")]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 11, 2), scheduled=True)

    assert loan.manual_balance == Decimal("-198500.00")


def test_a_transfer_rule_is_fulfilled_by_the_transfer_the_bank_recognised(db_session, provider, connected):
    ing, kid, spaar = connected["ing"].id, connected["kid"].id, connected["spaar_kid"].id
    # Recognisable through its number, so a rule paying into it lets the bank book the payment.
    bank_sync_repo.create_rule(db_session, text_contains="B 145-58977", gripr_account_id=spaar)
    rule = _rule(db_session, "Zakgeld Sam", T.TRANSFER, "10.00", ing, date(2026, 10, 26), counter_account_id=spaar)
    provider.transactions["uid-ing"] = [bank("10.00", date(2026, 10, 26), name="Sam", iban=KID)]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 27), scheduled=True)

    assert result.fulfilled == 1
    (row,) = all_rows(db_session)
    # What the bank actually did wins over what the rule assumed.
    assert (row.account_id, row.counter_account_id) == (ing, kid)
    assert rule.next_due_date == date(2026, 11, 26)


# -- recurring rules on bank-fed accounts ----------------------------------------------------


def test_a_bank_fed_rule_books_nothing_and_drops_its_pre_booked_occurrence(db_session, connected):
    ing = connected["ing"].id
    rule = _rule(db_session, "Spotify", T.EXPENSE, "12.99", ing, date(2026, 10, 9))
    gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 9), type=T.EXPENSE, amount=Decimal("12.99"), account_id=ing,
        source_ref=f"pefi_recurring:{rule.id}:2026-10-09",
    )

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 8))

    assert created == []
    assert all_rows(db_session) == []
    assert rule.next_due_date == date(2026, 10, 9)


def test_a_bank_fed_rule_moves_on_once_its_window_has_passed(db_session, connected):
    rule = _rule(db_session, "Spotify", T.EXPENSE, "12.99", connected["ing"].id, date(2026, 10, 9))

    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 14))
    assert rule.next_due_date == date(2026, 10, 9)  # still within BANK_FULFIL_DAYS

    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 15))
    assert rule.next_due_date == date(2026, 11, 9)
    assert all_rows(db_session) == []


def test_rules_elsewhere_keep_booking_and_switching_off_restores_the_rest(db_session, connected, ing):
    elsewhere = _rule(db_session, "Pot", T.TRANSFER, "75.00", connected["tr"].id, date(2026, 10, 9), counter_account_id=connected["spaar_kid"].id)
    on_ing = _rule(db_session, "Spotify", T.EXPENSE, "12.99", connected["ing"].id, date(2026, 10, 9))

    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 9))
    assert [r.amount for r in all_rows(db_session)] == [Decimal("75.00")]

    bank_sync_repo.update_connection(db_session, ing, enabled=False)
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 9))
    assert sorted(r.amount for r in all_rows(db_session)) == [Decimal("12.99"), Decimal("75.00")]
    assert elsewhere.next_due_date == on_ing.next_due_date == date(2026, 11, 9)


# -- connecting --------------------------------------------------------------------------------


def test_connecting_needs_the_server_configured(db_session, provider, ing, monkeypatch):
    monkeypatch.setattr(config, "ING_REDIRECT_URL", None)

    with pytest.raises(bank_sync_service.BankNotConfigured):
        bank_sync_service.start_connect(db_session, ing, provider)


def test_connect_round_trip_keeps_the_mapping_and_closes_the_old_session(db_session, provider, connected, ing, monkeypatch):
    monkeypatch.setattr(config, "ING_REDIRECT_URL", "https://ipper.example/api/gripr/ing/callback")

    url = bank_sync_service.start_connect(db_session, ing, provider)
    state = ing.pending_state

    assert url.startswith("https://")
    assert provider.started[0]["state"] == state
    assert provider.started[0]["redirect_url"] == "https://ipper.example/api/gripr/ing/callback"
    provider.session = BankSession(
        session_id="sess-2",
        valid_until=datetime(2027, 3, 30, 9, 0),
        accounts=[BankAccount(uid="uid-ing-2", iban=ING, product="Betaalrekening", holder_name="Hr J Jansen", currency="EUR")],
    )
    with pytest.raises(bank_sync_service.BankStateMismatch):
        bank_sync_service.complete_connect(db_session, "forged", "code", provider)

    assert bank_sync_service.complete_connect(db_session, state, "code", provider) is ing

    assert (ing.session_id, ing.pending_state) == ("sess-2", None)
    assert provider.deleted == ["sess-1"]
    ing_account = bank_sync_repo.get_account(db_session, ING)
    assert (ing_account.eb_uid, ing_account.gripr_account_id) == ("uid-ing-2", connected["ing"].id)
    assert bank_sync_repo.get_account(db_session, KID).eb_uid is None  # not in this consent


def test_disconnecting_switches_off_and_keeps_the_mapping(db_session, provider, connected, ing):
    bank_sync_service.disconnect(db_session, ing, provider)

    assert (ing.session_id, ing.enabled) == (None, False)
    assert provider.deleted == ["sess-1"]
    assert bank_sync_repo.get_account(db_session, ING).gripr_account_id == connected["ing"].id


@pytest.mark.parametrize(("maximum", "days"), [(15552000, 179), (7776000, 89), (None, 89)])
def test_a_consent_asks_for_a_day_less_than_the_banks_own_maximum(db_session, provider, ing, monkeypatch, maximum, days):
    # Trade Republic refuses a consent longer than its 90 days outright, rather than shortening it.
    monkeypatch.setattr(config, "ING_REDIRECT_URL", "https://ipper.example/api/gripr/ing/callback")
    provider.maximum_seconds = maximum
    now = datetime(2026, 10, 2, 12, 0)

    bank_sync_service.start_connect(db_session, ing, provider, now=now)

    assert provider.started[0]["valid_until"] == now + timedelta(days=days)


def test_a_second_bank_connects_on_its_own_state_and_keeps_its_accounts_apart(db_session, provider, trade_republic, ing, monkeypatch):
    monkeypatch.setattr(config, "ING_REDIRECT_URL", "https://ipper.example/api/gripr/ing/callback")
    bank_sync_service.start_connect(db_session, ing, provider)
    bank_sync_service.start_connect(db_session, trade_republic, provider)
    assert provider.started[1]["aspsp_name"] == "Trade Republic"
    provider.session = BankSession(
        session_id="sess-tr-2", valid_until=datetime(2026, 12, 31),
        accounts=[BankAccount(uid="uid-tr-2", iban=TR_CASH, product="Cash", holder_name="J Jansen", currency="EUR")],
    )

    bank_sync_service.complete_connect(db_session, trade_republic.pending_state, "code", provider)

    assert trade_republic.session_id == "sess-tr-2"
    assert ing.session_id == "sess-1"  # ING's consent untouched
    assert ing.pending_state is not None  # its own consent still pending, by its own state
    assert bank_sync_repo.get_account(db_session, ING).eb_uid == "uid-ing"


# -- two banks ---------------------------------------------------------------------------------


def tr_entry(amount: str, day: date, *, out: bool = True) -> BankTransaction:
    """What Trade Republic sends: date, amount, direction -- nothing else."""
    return bank(amount, day, out=out)


def test_money_from_ing_to_trade_republic_is_booked_once_by_ing(db_session, provider, trade_republic):
    provider.transactions["uid-ing"] = [bank("1000.00", date(2026, 10, 12), name="J Jansen", iban=TR_CASH)]
    provider.transactions["uid-tr"] = [tr_entry("1000.00", date(2026, 10, 12), out=False)]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 15), scheduled=True)

    assert (result.booked, result.matched) == (1, 1)  # ING books the transfer; Trade Republic's half finds it
    (row,) = all_rows(db_session)
    assert (row.type, row.source_ref[:4]) == (T.TRANSFER, "ing:")


def test_money_from_trade_republic_to_ing_is_booked_once_by_ing(db_session, provider, trade_republic, connected):
    # Trade Republic can't say where its debit went, so ING's half books it -- not skipped as a
    # "counterpart" the way a transfer between two ING accounts is.
    provider.transactions["uid-ing"] = [bank("750.00", date(2026, 10, 12), out=False, name="J Jansen", iban=TR_CASH)]
    provider.transactions["uid-tr"] = [tr_entry("750.00", date(2026, 10, 12))]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 15), scheduled=True)

    assert (result.booked, result.matched, result.counterparts) == (1, 1, 0)
    (row,) = all_rows(db_session)
    assert (row.type, row.account_id, row.counter_account_id) == (T.TRANSFER, connected["tr"].id, connected["ing"].id)


def test_before_trade_republic_starts_ing_still_books_the_transfer(db_session, provider, trade_republic, connected):
    # Trade Republic syncs from 10 Oct; a transfer it sent on the 5th is ING's to book.
    provider.transactions["uid-ing"] = [bank("750.00", date(2026, 10, 5), out=False, name="J Jansen", iban=TR_CASH)]
    provider.transactions["uid-tr"] = [tr_entry("750.00", date(2026, 10, 5))]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 11), scheduled=True)

    assert result.booked == 1
    (row,) = all_rows(db_session)
    assert (row.type, row.account_id, row.counter_account_id) == (T.TRANSFER, connected["tr"].id, connected["ing"].id)


def test_a_card_payment_you_entered_is_checked_off(db_session, provider, trade_republic, connected):
    # Typed in on the day of the purchase; Trade Republic books it two days later.
    gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 11), type=T.EXPENSE, amount=Decimal("26.42"), account_id=connected["tr"].id
    )
    provider.transactions["uid-tr"] = [tr_entry("26.42", date(2026, 10, 13))]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 16), scheduled=True)

    assert (result.matched, result.booked) == (1, 0)
    assert len(all_rows(db_session)) == 1


def test_a_payment_you_didnt_enter_is_booked_for_you_to_look_up(db_session, provider, trade_republic, connected):
    provider.transactions["uid-tr"] = [tr_entry("32.78", date(2026, 10, 13))]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 16), scheduled=True)

    (row,) = all_rows(db_session)
    assert (row.type, row.account_id, row.category_id) == (T.EXPENSE, connected["tr"].id, None)
    assert row.notes == "Trade Republic: not entered by hand — look it up in the Trade Republic app"
    assert row.source_ref.startswith("tr:")


def test_trade_republic_waits_two_days_so_your_own_entry_comes_first(db_session, provider, trade_republic, connected):
    provider.transactions["uid-tr"] = [tr_entry("26.42", date(2026, 10, 13))]

    first = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 14), scheduled=True)
    assert first == bank_sync_service.SyncResult()  # not yet, and not recorded either

    gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 12), type=T.EXPENSE, amount=Decimal("26.42"), account_id=connected["tr"].id
    )
    second = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 15), scheduled=True)
    assert (second.matched, second.booked) == (1, 0)


def test_an_amount_rule_books_the_monthly_savings_plan_as_a_transfer(db_session, provider, trade_republic, connected):
    invested = GriprAccount(name="Afschrijving Auto", type=GriprAccountType.INVESTMENT, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add(invested)
    db_session.flush()
    bank_sync_repo.create_rule(db_session, amount=Decimal("121.00"), day_of_month=2, gripr_account_id=invested.id)
    provider.transactions["uid-tr"] = [
        tr_entry("121.00", date(2026, 11, 3)),   # the savings plan, a day late around a weekend
        tr_entry("121.00", date(2026, 11, 17)),  # a purchase that happens to cost the same
    ]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 11, 20), scheduled=True)

    plan, purchase = sorted(all_rows(db_session), key=lambda r: r.date)
    assert (plan.type, plan.account_id, plan.counter_account_id) == (T.TRANSFER, connected["tr"].id, invested.id)
    assert plan.notes == "Trade Republic: transfer recognised by its amount and date"
    assert (purchase.type, purchase.counter_account_id) == (T.EXPENSE, None)


def test_a_saveback_month_reward_in_and_purchase_out(db_session, provider, trade_republic, connected):
    cashback = GriprAccount(name="Cashback", type=GriprAccountType.SAVINGS, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add(cashback)
    db_session.flush()
    bank_sync_repo.create_rule(db_session, amount_max=Decimal("15.00"), day_of_month=2, direction="out", gripr_account_id=cashback.id)
    gripr_transaction_repo.create_transaction(  # a coffee you typed in, the same week
        db_session, date=date(2026, 11, 3), type=T.EXPENSE, amount=Decimal("3.95"), account_id=connected["tr"].id
    )
    provider.transactions["uid-tr"] = [
        tr_entry("7.12", date(2026, 11, 1), out=False),  # the saveback reward
        tr_entry("7.12", date(2026, 11, 2)),             # ...invested in the S&P 500 the next day
        tr_entry("3.95", date(2026, 11, 3)),             # the coffee: yours, not a saveback
        tr_entry("40.00", date(2026, 11, 2)),            # too much to be a saveback
    ]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 11, 10), scheduled=True)

    assert result.matched == 1
    booked = {(r.type, r.amount): r for r in all_rows(db_session) if r.source_ref and r.source_ref.startswith("tr:")}
    reward, purchase, other = booked[(T.INCOME, Decimal("7.12"))], booked[(T.TRANSFER, Decimal("7.12"))], booked[(T.EXPENSE, Decimal("40.00"))]
    assert reward.category_id is None  # yours to file under Cashback
    assert (purchase.account_id, purchase.counter_account_id) == (connected["tr"].id, cashback.id)
    assert other.counter_account_id is None


@pytest.fixture()
def pot(db_session, connected):
    """Onderhoud Auto: money set aside on paper, really sitting in Trade Republic."""
    account = GriprAccount(
        name="Onderhoud Auto", type=GriprAccountType.SAVINGS, balance_mode=GriprBalanceMode.TRANSACTIONAL,
        held_in_account_id=connected["tr"].id,
    )
    db_session.add(account)
    db_session.flush()
    return account


def test_spending_from_a_pot_is_the_parent_accounts_bank_entry(db_session, provider, trade_republic, connected, pot):
    gripr_transaction_repo.create_transaction(  # the repair, booked on the pot it's paid from
        db_session, date=date(2026, 10, 12), type=T.EXPENSE, amount=Decimal("2511.03"), account_id=pot.id
    )
    provider.transactions["uid-tr"] = [tr_entry("2511.03", date(2026, 10, 13))]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 16), scheduled=True)

    assert (result.matched, result.booked) == (1, 0)


def test_money_set_aside_in_a_pot_never_matches_a_real_payment(db_session, provider, trade_republic, connected, pot):
    gripr_transaction_repo.create_transaction(  # this month's €75 into the pot -- invisible to the bank
        db_session, date=date(2026, 10, 25), type=T.TRANSFER, amount=Decimal("75.00"),
        account_id=connected["tr"].id, counter_account_id=pot.id,
    )
    provider.transactions["uid-tr"] = [tr_entry("75.00", date(2026, 10, 25))]  # a real €75 card payment

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 28), scheduled=True)

    assert (result.matched, result.booked) == (0, 1)


def test_trade_republic_rules_book_on_their_own_date_and_the_bank_checks_them_off(db_session, provider, trade_republic, connected, pot):
    tr = connected["tr"].id
    insurance = GriprCategory(name="Verzekering", kind=GriprCategoryKind.EXPENSE)
    db_session.add(insurance)
    db_session.flush()
    bank_sync_repo.create_rule(db_session, text_contains="Onderhoud", gripr_account_id=pot.id)  # even if a rule names the pot
    set_aside = _rule(db_session, "Onderhoud Focus", T.TRANSFER, "75.00", tr, date(2026, 10, 25), counter_account_id=pot.id)
    paid_from_pot = _rule(db_session, "APK", T.EXPENSE, "60.00", pot.id, date(2026, 10, 20), category_id=insurance.id)

    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 25))

    # Trade Republic's entries arrive days late and say nothing, so nothing waits for them.
    assert sorted((r.amount, r.account_id) for r in all_rows(db_session)) == [(Decimal("60.00"), pot.id), (Decimal("75.00"), tr)]
    assert set_aside.next_due_date == date(2026, 11, 25)
    assert paid_from_pot.next_due_date == date(2026, 11, 20)

    provider.transactions["uid-tr"] = [tr_entry("60.00", date(2026, 10, 21))]
    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 25), scheduled=True)

    assert (result.matched, result.booked, result.fulfilled) == (1, 0, 0)
    assert len(all_rows(db_session)) == 2


def test_each_bank_keeps_its_own_reference_space(db_session, provider, trade_republic):
    provider.transactions["uid-ing"] = [bank("5.00", date(2026, 10, 12), ref="000123")]
    provider.transactions["uid-tr"] = [bank("6.00", date(2026, 10, 12), ref="000123")]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 15), scheduled=True)

    assert result.booked == 2
    assert sorted(r.source_ref for r in all_rows(db_session)) == ["ing:000123", "tr:000123"]


def test_one_bank_failing_doesnt_stop_the_other(db_session, provider, trade_republic, ing):
    bank_sync_repo.update_connection(db_session, trade_republic, session_id=None)
    provider.transactions["uid-ing"] = [bank("12.99", date(2026, 10, 12), name="Spotify")]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 13), scheduled=True)

    assert result.booked == 1
    assert result.problems == {"Trade Republic": "not connected"}
    assert ing.last_synced_at is not None
    assert trade_republic.last_synced_at is None


def test_a_savings_plan_rule_books_ahead_and_the_plans_bank_entry_checks_it_off(db_session, provider, trade_republic, connected):
    tr = connected["tr"].id
    invested = GriprAccount(name="Afschrijving Auto", type=GriprAccountType.INVESTMENT, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add(invested)
    db_session.flush()
    bank_sync_repo.create_rule(db_session, amount=Decimal("121.00"), day_of_month=2, direction="out", gripr_account_id=invested.id)
    plan = _rule(db_session, "TDIV plan", T.TRANSFER, "121.00", tr, date(2026, 11, 2), counter_account_id=invested.id)

    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 31))  # booked 2 days ahead
    provider.transactions["uid-tr"] = [tr_entry("121.00", date(2026, 11, 3))]
    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 11, 6), scheduled=True)

    assert plan.next_due_date == date(2026, 11, 2)  # pre-booked; the rule still names that date
    assert (result.matched, result.booked) == (1, 0)
    (row,) = all_rows(db_session)
    assert (row.type, row.amount, row.account_id, row.counter_account_id) == (T.TRANSFER, Decimal("121.00"), tr, invested.id)


def test_uncategorised_filter_lists_what_still_needs_filing(db_session, accounts):
    ing, tr = accounts["ing"].id, accounts["tr"].id
    food = GriprCategory(name="Boodschappen", kind=GriprCategoryKind.EXPENSE)
    db_session.add(food)
    db_session.flush()
    for fields in (
        dict(type=T.EXPENSE, amount=Decimal("1"), account_id=ing),
        dict(type=T.EXPENSE, amount=Decimal("2"), account_id=ing, category_id=food.id),
        dict(type=T.TRANSFER, amount=Decimal("3"), account_id=ing, counter_account_id=tr),
        dict(type=T.INCOME, amount=Decimal("4"), account_id=ing),
    ):
        gripr_transaction_repo.create_transaction(db_session, date=date(2026, 10, 4), **fields)

    items, total = gripr_transaction_repo.list_transactions(db_session, uncategorized=True)

    assert total == 2
    assert sorted(t.amount for t in items) == [Decimal("1"), Decimal("4")]


# -- Trading 212 (docs/adr/0031) ---------------------------------------------------------------


class FakeTrading212:
    configured = True

    def __init__(self):
        self.entries: list[CashEntry] = []
        self.sinces: list[date] = []
        self.error: Exception | None = None

    def cash_activity(self, since, until=None):
        if self.error is not None:
            raise self.error
        self.sinces.append(since)
        return list(self.entries)


def t212_entry(amount: str, day: date, action: str = "Card debit", merchant: str = "", category: str = "", ref: str | None = None) -> CashEntry:
    global _counter
    _counter += 1
    return CashEntry(
        entry_id=ref or f"t212-{_counter:06d}", action=action, at=datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc),
        amount=Decimal(amount), currency="EUR", merchant=merchant, merchant_category=category,
    )


@pytest.fixture()
def t212():
    return FakeTrading212()


@pytest.fixture()
def trading212(db_session, connected) -> BankConnection:
    """Trading 212 read with the server's API key -- no consent -- booking into T212 Debit."""
    connection = _connection(db_session, "Trading 212", "t212", provider="trading212", enabled=True, since=SINCE)
    bank_sync_repo.upsert_account(db_session, "T212", connection_id=connection.id, product="Invest account", gripr_account_id=connected["t212"].id)
    return connection


def test_a_card_payment_is_booked_with_its_merchant_and_interest_is_left_to_gainr(db_session, provider, t212, trading212, connected):
    t212.entries = [
        t212_entry("-15.99", date(2026, 10, 4), merchant="Netflix", category="UTILITIES"),
        t212_entry("0.11", date(2026, 10, 4), action="Spending cashback"),
        t212_entry("0.05", date(2026, 10, 4), action="Interest on cash"),
        t212_entry("-0.18", date(2026, 10, 4), action="Currency conversion"),
    ]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), t212=t212, scheduled=True)

    assert result.booked == 1
    (row,) = all_rows(db_session)
    assert (row.type, row.amount, row.account_id, row.category_id) == (T.EXPENSE, Decimal("15.99"), connected["t212"].id, None)
    assert row.notes == "Netflix — Utilities"
    assert row.source_ref.startswith("t212:")
    assert t212.sinces == [SINCE]


def test_a_card_payment_takes_the_category_last_given_at_that_merchant(db_session, provider, t212, trading212, connected):
    groceries = GriprCategory(name="Boodschappen", kind=GriprCategoryKind.EXPENSE)
    db_session.add(groceries)
    db_session.flush()
    gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 3), type=T.EXPENSE, amount=Decimal("27.39"), account_id=connected["t212"].id, category_id=groceries.id
    )
    t212.entries = [
        t212_entry("-27.39", date(2026, 10, 3), merchant="Jumbo", category="RETAIL_STORES"),  # the one entered by hand
        t212_entry("-11.07", date(2026, 10, 5), merchant="JUMBO", category="RETAIL_STORES"),
        t212_entry("-6.00", date(2026, 10, 5), merchant="QPark", category="BUSINESS_SERVICES"),
    ]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), t212=t212, scheduled=True)

    assert (result.matched, result.booked) == (1, 2)
    _, jumbo, qpark = all_rows(db_session)
    assert jumbo.category_id == groceries.id
    assert qpark.category_id is None  # a merchant never categorised stays for the reader


def test_a_card_payment_fulfils_its_recurring_rule(db_session, provider, t212, trading212, connected):
    insurance = GriprCategory(name="Verzekering", kind=GriprCategoryKind.EXPENSE)
    db_session.add(insurance)
    db_session.flush()
    rule = _rule(db_session, "Allianz", T.EXPENSE, "41.50", connected["t212"].id, date(2026, 10, 25), category_id=insurance.id)
    t212.entries = [t212_entry("-41.50", date(2026, 10, 25), merchant="Allianz", category="SERVICE_PROVIDERS")]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 26), t212=t212, scheduled=True)

    assert result.fulfilled == 1
    assert all_rows(db_session)[0].category_id == insurance.id
    assert rule.next_due_date == date(2026, 11, 25)


def test_a_top_up_waits_then_claims_the_transfer_ing_booked(db_session, provider, t212, trading212, connected):
    bank_sync_repo.create_rule(db_session, iban=ADYEN, text_contains="Trading 212", gripr_account_id=connected["t212"].id)
    provider.transactions["uid-ing"] = [bank("500.00", date(2026, 10, 4), name="Trading 212 via Adyen", iban=ADYEN, description="Trading 212")]
    t212.entries = [t212_entry("500.00", date(2026, 10, 4), action="Deposit")]

    first = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), t212=t212, scheduled=True)
    later = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 7), t212=t212, scheduled=True)

    assert (first.booked, first.matched) == (1, 0)  # ING's half; Trading 212's waits its two days
    assert (later.booked, later.matched) == (0, 1)
    (transfer,) = all_rows(db_session)
    assert (transfer.type, transfer.account_id, transfer.counter_account_id) == (T.TRANSFER, connected["ing"].id, connected["t212"].id)


def test_money_moved_to_the_investment_account_never_matches_a_card_payment(db_session, provider, t212, trading212, connected):
    from app.models.broker_sync import BrokerConnection
    from app.models.gripr_portfolio_link import GriprPortfolioLink
    from app.models.portfolio import Portfolio

    beleggen = GriprAccount(name="Beleggen", type=GriprAccountType.INVESTMENT, balance_mode=GriprBalanceMode.MANUAL)
    main = Portfolio(name="Main")
    db_session.add_all([beleggen, main])
    db_session.flush()
    db_session.add_all([
        GriprPortfolioLink(account_id=beleggen.id, portfolio_id=main.id),
        BrokerConnection(broker="Trading212", portfolio_id=main.id, enabled=True, since=SINCE),
    ])
    gripr_transaction_repo.create_transaction(
        db_session, date=date(2026, 10, 4), type=T.TRANSFER, amount=Decimal("300.00"), account_id=connected["t212"].id,
        counter_account_id=beleggen.id,
    )
    t212.entries = [t212_entry("-300.00", date(2026, 10, 4), merchant="Coolblue", category="ELECTRONICS")]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), t212=t212, scheduled=True)

    # Both are the same cash at Trading 212: investing it is never a Trading 212 entry of its own.
    assert (result.matched, result.booked) == (0, 1)


def test_a_refused_trading212_key_is_reported_and_ing_still_syncs(db_session, provider, t212, trading212, connected):
    t212.error = Trading212AuthError("refused")
    provider.transactions["uid-ing"] = [bank("12.99", date(2026, 10, 4), name="Spotify")]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), t212=t212, scheduled=True)

    assert result.problems == {"Trading 212": "API key refused"}
    assert result.booked == 1
    assert "IP address" in trading212.last_error


def test_trading212_without_a_key_is_not_configured(db_session, provider, t212, trading212):
    t212.configured = False

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 5), t212=t212, scheduled=True)

    assert result.problems == {"Trading 212": "not configured"}
    assert not bank_sync_service.is_connected(trading212, t212=t212)


def test_trading212_has_nothing_to_connect_or_end(db_session, provider, trading212, monkeypatch):
    monkeypatch.setattr(config, "ING_REDIRECT_URL", "https://ipper.example/api/gripr/ing/callback")

    with pytest.raises(bank_sync_service.BankNotConfigured):
        bank_sync_service.start_connect(db_session, trading212, provider)
    bank_sync_service.disconnect(db_session, trading212, provider)
    assert not trading212.enabled
    assert provider.deleted == []


def test_an_amount_rule_leaves_a_card_payment_that_names_its_shop_alone(db_session, provider, t212, trading212, connected):
    # The Trade Republic saveback rule: money out, at most €15, around the 2nd.
    bank_sync_repo.create_rule(db_session, amount_max=Decimal("15.00"), day_of_month=2, direction="out", gripr_account_id=connected["tr"].id)
    t212.entries = [t212_entry("-8.00", date(2026, 10, 3), merchant="Jumbo", category="RETAIL_STORES")]
    provider.transactions["uid-ing"] = [bank("12.50", date(2026, 10, 3), name="Albert Heijn")]

    bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 4), t212=t212, scheduled=True)

    assert {(r.type, r.amount) for r in all_rows(db_session)} == {(T.EXPENSE, Decimal("8.00")), (T.EXPENSE, Decimal("12.50"))}


def test_a_repayment_from_the_named_person_is_booked_as_their_refund(db_session, provider, connected):
    restaurants = GriprCategory(name="Restaurants", kind=GriprCategoryKind.EXPENSE)
    db_session.add(restaurants)
    db_session.flush()
    dinner = gripr_transaction_service.create_transaction(
        db_session, date=date(2026, 10, 3), type=T.EXPENSE, amount=Decimal("100.00"), account_id=connected["ing"].id,
        category_id=restaurants.id, expected_back=Decimal("75.00"), expected_from="Jan de Vries",
    )
    provider.transactions["uid-ing"] = [
        bank("100.00", date(2026, 10, 3), name="Restaurant De Haven"),  # the bill itself, matched
        bank("25.00", date(2026, 10, 5), out=False, name="AAB INZ TIKKIE", description="Tikkie ID 0012, J de Vries, Etentje"),
        bank("25.00", date(2026, 10, 5), out=False, name="AAB INZ TIKKIE", description="Tikkie ID 0013, Piet, Etentje"),
    ]

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 6), scheduled=True)

    assert (result.matched, result.booked) == (1, 2)
    jan, piet = [r for r in all_rows(db_session) if r.id != dinner.id]
    assert (jan.type, jan.refund_of_id, jan.category_id) == (T.REFUND, dinner.id, restaurants.id)
    assert (piet.type, piet.refund_of_id) == (T.INCOME, None)  # not named on the dinner: left for you


def test_sync_now_leaves_trade_republic_to_the_morning_run(db_session, provider, trade_republic):
    provider.transactions["uid-tr"] = [tr_entry("26.42", date(2026, 10, 11))]

    manual = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 14))

    assert manual.booked == 0
    assert trade_republic.last_synced_at is None  # not read at all
    assert bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 14), scheduled=True).booked == 1


def test_a_refused_read_says_to_wait_for_tomorrow(db_session, provider, trade_republic):
    from app.services.enablebanking_provider import EnableBankingRateLimitError

    def refuse(session_id, account_uid, iban, date_from):
        if account_uid == "uid-tr":
            raise EnableBankingRateLimitError("Enable Banking answered 429")
        return []

    provider.get_transactions = refuse

    result = bank_sync_service.sync(db_session, provider, as_of=date(2026, 10, 14), scheduled=True)

    assert result.problems == {"Trade Republic": "daily read limit reached"}
    assert "tomorrow morning" in trade_republic.last_error
    assert trade_republic.session_id is not None  # still connected: nothing to reconnect
