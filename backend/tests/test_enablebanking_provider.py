from datetime import date, datetime
from decimal import Decimal

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.enablebanking_provider import (
    EnableBankingError,
    EnableBankingProvider,
    EnableBankingSessionError,
    _parse_session,
    _fill_missing_references,
    _parse_transaction,
    describe,
)

ING = "NL11INGB0001234567"

# Shapes as ING returns them through Enable Banking (amounts and names from a real export).
INCASSO = {
    "entry_reference": "010305312566556890000000",
    "transaction_amount": {"currency": "EUR", "amount": "9.30"},
    "creditor": {"name": "Verzekeraar N.V."},
    "creditor_account": {"iban": "NL55RABO0003334445"},
    "debtor_account": {"iban": ING},
    "bank_transaction_code": {"description": "Incasso"},
    "credit_debit_indicator": "DBIT",
    "status": "BOOK",
    "booking_date": "2026-10-01",
    "transaction_date": "2026-09-30",
    "remittance_information": [
        "Naam: Verzekeraar N.V.",
        "Omschrijving: Uw premie met",
        "factuurnummer 202609280000000001",
        "IBAN: NL55RABO0003334445",
        "Kenmerk: 202609280000000001",
        "Machtiging ID: NL00ZZZ000000000",
        "Incassant ID: NL44ZZZ080277730000",
        "Doorlopende incasso",
        "Valutadatum: 01-10-2026",
    ],
}
CREDIT = {
    "entry_reference": "010305311419101190000000",
    "transaction_amount": {"currency": "EUR", "amount": "300.00"},
    "debtor": {"name": "Sociale Verzekeringsbank"},
    "debtor_account": {"iban": "NL44 RABO 0002 2233 34"},
    "creditor_account": {"iban": ING},
    "bank_transaction_code": {"description": "Overschrijving"},
    "credit_debit_indicator": "CRDT",
    "status": "BOOK",
    "booking_date": "2026-10-01",
    "remittance_information": [
        "Naam: Sociale Verzekeringsbank",
        "Omschrijving: KINDERBIJSLAG 3e",
        "kwart. 26 PA18550680 WWW.SVB.NL",
        "Sociale Verzekeringsbank",
        "IBAN: NL44RABO0002223334",
        "Valutadatum: 01-10-2026",
    ],
}


def test_describe_joins_a_wrapped_omschrijving_and_drops_the_bookkeeping():
    assert describe(INCASSO["remittance_information"], "Verzekeraar N.V.") == "Uw premie met factuurnummer 202609280000000001"


def test_describe_drops_the_collector_repeating_its_own_name():
    assert describe(CREDIT["remittance_information"], "Sociale Verzekeringsbank") == "KINDERBIJSLAG 3e kwart. 26 PA18550680 WWW.SVB.NL"


def test_describe_falls_back_to_free_text_lines_for_bank_fees_and_savings_transfers():
    lines = ["Kosten Betaalpas gemachtigde", "1 aug t/m 31 aug 2026", "ING BANK N.V.", "Valutadatum: 12-09-2026"]
    assert describe(lines, "") == "Kosten Betaalpas gemachtigde · 1 aug t/m 31 aug 2026 · ING BANK N.V."
    assert describe(["Naar Oranje spaarrekening B14558977", "Valutadatum: 26-09-2026"], "") == "Naar Oranje spaarrekening B14558977"


def test_parses_a_debit_with_its_counterparty_and_transaction_date():
    txn = _parse_transaction(INCASSO, ING)

    assert txn.reference == "010305312566556890000000"
    assert (txn.amount, txn.is_debit, txn.currency) == (Decimal("9.30"), True, "EUR")
    assert (txn.booked_on, txn.transacted_on) == (date(2026, 10, 1), date(2026, 9, 30))
    assert (txn.counterparty_name, txn.counterparty_iban) == ("Verzekeraar N.V.", "NL55RABO0003334445")
    assert txn.method == "Incasso"


def test_parses_a_credit_from_the_debtor_side_and_compacts_the_iban():
    txn = _parse_transaction(CREDIT, ING)

    assert txn.is_debit is False
    assert (txn.counterparty_name, txn.counterparty_iban) == ("Sociale Verzekeringsbank", "NL44RABO0002223334")
    assert txn.transacted_on == date(2026, 10, 1)  # no transaction_date: the booking date


@pytest.mark.parametrize(
    "change",
    [
        {"status": "PDNG"},
        {"transaction_amount": {"currency": "EUR", "amount": "0.00"}},
        {"transaction_amount": {"currency": "EUR", "amount": "NaN"}},
        {"transaction_amount": {"currency": "EUR", "amount": "lots"}},
        {"booking_date": "yesterday"},
        {"credit_debit_indicator": "?"},
    ],
)
def test_skips_anything_not_booked_or_not_well_formed(change):
    assert _parse_transaction({**INCASSO, **change}, ING) is None


def test_a_signed_amount_keeps_only_its_size():
    # Trade Republic signs debits ("-121.000000") on top of the DBIT indicator.
    txn = _parse_transaction({**INCASSO, "transaction_amount": {"currency": "EUR", "amount": "-121.000000"}}, ING)

    assert (txn.amount, txn.is_debit) == (Decimal("121.00"), True)


# What Trade Republic sends through Enable Banking: nothing but date, amount and direction.
def amount_only(amount: str, day: str, indicator: str = "DBIT") -> dict:
    return {"transaction_amount": {"currency": "EUR", "amount": amount}, "credit_debit_indicator": indicator, "status": "BOOK", "booking_date": day}


def test_entries_without_a_reference_get_a_stable_one_that_keeps_twins_apart():
    entries = [amount_only("-3.95", "2026-10-02"), amount_only("-3.95", "2026-10-02"), amount_only("-6.60", "2026-10-02")]
    first = [_parse_transaction(e, ING) for e in entries]
    again = [_parse_transaction(dict(e), ING) for e in entries]

    _fill_missing_references(first, ING)
    _fill_missing_references(again, ING)

    assert all(t.reference.startswith("h") for t in first)
    assert len({t.reference for t in first}) == 3  # two identical coffees stay two entries
    assert [t.reference for t in first] == [t.reference for t in again]


def test_a_bank_reference_is_left_alone():
    txn = _parse_transaction(INCASSO, ING)
    _fill_missing_references([txn], ING)

    assert txn.reference == "010305312566556890000000"


def test_parses_a_session_keyed_on_ibans():
    session = _parse_session(
        {
            "session_id": "891cbf3e",
            "access": {"valid_until": "2027-03-30T09:11:14Z"},
            "accounts": [
                {"uid": "u1", "account_id": {"iban": ING}, "product": "Betaalrekening", "name": "Hr J Jansen", "currency": "EUR"},
                {"uid": "u2", "account_id": {"iban": None}},  # no IBAN: unusable
            ],
        }
    )

    assert session.session_id == "891cbf3e"
    assert session.valid_until == datetime(2027, 3, 30, 9, 11, 14)
    assert [(a.uid, a.iban, a.product) for a in session.accounts] == [("u1", ING, "Betaalrekening")]


@pytest.fixture()
def key_file(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "app.pem"
    path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return path, key.public_key()


def test_signs_a_short_lived_rs256_token_naming_the_app(key_file):
    path, public_key = key_file
    provider = EnableBankingProvider("app-123", str(path))

    token = provider._token()

    assert jwt.get_unverified_header(token)["kid"] == "app-123"
    claims = jwt.decode(token, public_key, algorithms=["RS256"], audience="api.enablebanking.com")
    assert claims["iss"] == "enablebanking.com"
    assert claims["exp"] - claims["iat"] <= 86400


def test_an_unconfigured_or_unreadable_key_is_an_error(tmp_path):
    with pytest.raises(EnableBankingError):
        EnableBankingProvider(None, None)._token()
    with pytest.raises(EnableBankingError):
        EnableBankingProvider("app", str(tmp_path / "missing.pem"))._token()


def test_reads_every_page_of_transactions(monkeypatch):
    provider = EnableBankingProvider("app", "key")
    pages = [
        {"transactions": [INCASSO], "continuation_key": "next"},
        {"transactions": [CREDIT, {**INCASSO, "status": "PDNG"}], "continuation_key": None},
    ]
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append(kwargs["params"])
        return pages[len(calls) - 1]

    monkeypatch.setattr(provider, "_request", fake_request)

    txns = provider.get_transactions("sess", "uid", ING, date(2026, 9, 1))

    assert [t.amount for t in txns] == [Decimal("9.30"), Decimal("300.00")]
    assert calls == [{"date_from": "2026-09-01"}, {"date_from": "2026-09-01", "continuation_key": "next"}]


def test_a_bank_ignoring_the_start_date_is_cut_off_there(monkeypatch):
    # Trade Republic pages through its whole history, newest first; each page costs one of the few
    # reads a day it allows.
    provider = EnableBankingProvider("app", "key")
    pages = [
        {"transactions": [amount_only("-26.42", "2026-10-02"), amount_only("-5.00", "2026-09-28")], "continuation_key": "p2"},
        {"transactions": [amount_only("-7.00", "2026-09-20"), amount_only("-8.00", "2026-09-10")], "continuation_key": "p3"},
        {"transactions": [amount_only("-9.00", "2026-08-01")], "continuation_key": "p4"},
    ]
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append(kwargs["params"])
        return pages[len(calls) - 1]

    monkeypatch.setattr(provider, "_request", fake_request)

    txns = provider.get_transactions("sess", "uid", "NL33TRBK0001112223", date(2026, 9, 25))

    assert [t.amount for t in txns] == [Decimal("26.42"), Decimal("5.00")]
    assert len(calls) == 2  # the second page held nothing new enough, so no third read


def test_a_failure_on_an_expired_session_asks_for_a_reconnect(monkeypatch):
    provider = EnableBankingProvider("app", "key")

    def fake_request(method, path, **kwargs):
        if path.startswith("/sessions/"):
            return {"status": "EXPIRED"}
        raise EnableBankingError("Enable Banking answered 401")

    monkeypatch.setattr(provider, "_request", fake_request)

    with pytest.raises(EnableBankingSessionError):
        provider.get_transactions("sess", "uid", ING, date(2026, 10, 3))


def test_a_failure_on_a_live_session_stays_a_plain_error(monkeypatch):
    provider = EnableBankingProvider("app", "key")

    def fake_request(method, path, **kwargs):
        if path.startswith("/sessions/"):
            return {"status": "AUTHORIZED"}
        raise EnableBankingError("Enable Banking answered 500")

    monkeypatch.setattr(provider, "_request", fake_request)

    with pytest.raises(EnableBankingError) as raised:
        provider.get_transactions("sess", "uid", ING, date(2026, 10, 3))
    assert not isinstance(raised.value, EnableBankingSessionError)


def test_reads_a_banks_maximum_consent_from_the_bank_list(monkeypatch):
    provider = EnableBankingProvider("app", "key")
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append((path, kwargs.get("params")))
        return {"aspsps": [{"name": "ING", "maximum_consent_validity": 15552000}, {"name": "Trade Republic", "maximum_consent_validity": 7776000}]}

    monkeypatch.setattr(provider, "_request", fake_request)

    assert provider.maximum_consent_seconds("Trade Republic", "NL") == 7776000
    assert provider.maximum_consent_seconds("Bunq", "NL") is None
    assert calls[0] == ("/aspsps", {"country": "NL"})



def test_paging_stops_at_the_first_page_reaching_back_past_the_start(monkeypatch):
    provider = EnableBankingProvider("app", "key")
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append(kwargs["params"])
        return {"transactions": [amount_only("-26.42", "2026-10-02"), amount_only("-5.00", "2026-09-20")], "continuation_key": "p2"}

    monkeypatch.setattr(provider, "_request", fake_request)

    txns = provider.get_transactions("sess", "uid", "NL33TRBK0001112223", date(2026, 9, 25))

    assert [t.amount for t in txns] == [Decimal("26.42")]
    assert len(calls) == 1  # one read a day, not two


def test_a_rate_limited_read_doesnt_ask_about_the_session(monkeypatch):
    from app.services.enablebanking_provider import EnableBankingRateLimitError

    provider = EnableBankingProvider("app", "key")
    paths = []

    def fake_request(method, path, **kwargs):
        paths.append(path)
        raise EnableBankingRateLimitError("Enable Banking answered 429")

    monkeypatch.setattr(provider, "_request", fake_request)

    with pytest.raises(EnableBankingRateLimitError):
        provider.get_transactions("sess", "uid", "NL33TRBK0001112223", date(2026, 9, 25))
    assert paths == ["/accounts/uid/transactions"]
