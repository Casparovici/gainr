import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.bank_sync import BankConnection
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.repositories import bank_sync_repo
from app.routers import gripr as gripr_router

ING = "NL11INGB0001234567"


@pytest.fixture()
def client(db_session):
    # Only the router under test, rather than app.main -- importing that would run create_all
    # against the real portfolio.db.
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def banks(db_session) -> tuple[BankConnection, BankConnection]:
    """The two rows the migration seeds."""
    ing = BankConnection(aspsp_name="ING", aspsp_country="NL", source_prefix="ing")
    tr = BankConnection(aspsp_name="Trade Republic", aspsp_country="NL", source_prefix="tr", amount_only=True)
    db_session.add_all([ing, tr])
    db_session.flush()
    return ing, tr


@pytest.fixture()
def account_id(db_session) -> int:
    account = GriprAccount(name="ING", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add(account)
    db_session.flush()
    return account.id


def test_status_lists_every_bank_off_and_unconnected(client, banks):
    body = client.get("/api/gripr/banks").json()

    assert [(c["name"], c["connected"], c["enabled"], c["amount_only"]) for c in body["connections"]] == [
        ("ING", False, False, False),
        ("Trade Republic", False, False, True),
    ]
    assert body["rules"] == []


def test_switching_a_bank_on_without_a_date_starts_today_and_off_keeps_it(client, banks):
    ing, tr = banks
    body = client.put(f"/api/gripr/banks/{tr.id}", json={"enabled": True}).json()

    trade_republic = body["connections"][1]
    assert trade_republic["enabled"] is True
    assert trade_republic["since"] is not None
    assert body["connections"][0]["enabled"] is False  # ING untouched
    off = client.put(f"/api/gripr/banks/{tr.id}", json={"enabled": False}).json()
    assert off["connections"][1]["since"] == trade_republic["since"]


def test_mapping_an_account_and_adding_and_removing_a_rule(client, db_session, banks, account_id):
    bank_sync_repo.upsert_account(db_session, ING, connection_id=banks[0].id, eb_uid="uid", product="Betaalrekening")

    mapped = client.put(f"/api/gripr/banks/accounts/{ING}", json={"gripr_account_id": account_id}).json()
    ing_accounts = mapped["connections"][0]["accounts"]
    assert (ing_accounts[0]["gripr_account_id"], ing_accounts[0]["in_consent"]) == (account_id, True)
    assert mapped["connections"][1]["accounts"] == []

    added = client.post("/api/gripr/banks/rules", json={"iban": "nl33 trbk 0001 1122 23", "gripr_account_id": account_id}).json()
    assert added["rules"][0]["iban"] == "NL33TRBK0001112223"
    removed = client.delete(f"/api/gripr/banks/rules/{added['rules'][0]['id']}").json()
    assert removed["rules"] == []


def test_an_amount_rule_around_a_day_of_the_month(client, account_id):
    body = client.post("/api/gripr/banks/rules", json={"amount": "121.00", "day_of_month": 2, "gripr_account_id": account_id}).json()

    assert (body["rules"][0]["amount"], body["rules"][0]["day_of_month"]) == ("121.00", 2)
    assert client.post("/api/gripr/banks/rules", json={"day_of_month": 2, "gripr_account_id": account_id}).status_code == 422
    assert client.post("/api/gripr/banks/rules", json={"amount": "-5", "gripr_account_id": account_id}).status_code == 422


def test_a_saveback_rule_with_a_ceiling_and_a_direction(client, account_id):
    body = client.post(
        "/api/gripr/banks/rules",
        json={"amount_max": "15", "day_of_month": 2, "direction": "out", "gripr_account_id": account_id},
    ).json()

    rule = body["rules"][0]
    assert (rule["amount_max"], rule["direction"], rule["amount"]) == ("15.00", "out", None)
    both = {"amount": "121", "amount_max": "150", "gripr_account_id": account_id}
    assert client.post("/api/gripr/banks/rules", json=both).status_code == 422
    sideways = {"amount": "121", "direction": "sideways", "gripr_account_id": account_id}
    assert client.post("/api/gripr/banks/rules", json=sideways).status_code == 422


def test_a_rule_needs_something_to_match_on(client, account_id):
    assert client.post("/api/gripr/banks/rules", json={"gripr_account_id": account_id}).status_code == 422
    assert client.post("/api/gripr/banks/rules", json={"iban": "not an iban", "gripr_account_id": account_id}).status_code == 422


def test_unknown_things_are_404(client, banks, account_id):
    assert client.put("/api/gripr/banks/accounts/NL00XXXX0000000000", json={"gripr_account_id": account_id}).status_code == 404
    assert client.post("/api/gripr/banks/rules", json={"text_contains": "x", "gripr_account_id": 999}).status_code == 404
    assert client.put("/api/gripr/banks/99", json={"enabled": True}).status_code == 404
    assert client.post("/api/gripr/banks/99/connect").status_code == 404


@pytest.mark.parametrize(
    ("query", "outcome"),
    [
        ("error=access_denied&state=s", "cancelled"),
        ("state=forged&code=c", "failed"),
    ],
)
def test_the_callback_always_lands_on_accounts_without_echoing_the_bank(client, db_session, banks, query, outcome):
    bank_sync_repo.update_connection(db_session, banks[1], pending_state="the-real-state")

    response = client.get(f"/api/gripr/ing/callback?{query}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/gripr?bank={outcome}"


def test_sync_reports_a_bank_without_a_consent_instead_of_failing(client, banks):
    client.put(f"/api/gripr/banks/{banks[0].id}", json={"enabled": True})

    response = client.post("/api/gripr/banks/sync")

    assert response.status_code == 200
    assert response.json()["problems"] == {"ING": "not connected"}


def test_an_account_can_be_a_pot_one_level_deep(client, db_session, account_id):
    def make(name):
        account = GriprAccount(name=name, type=GriprAccountType.SAVINGS, balance_mode=GriprBalanceMode.TRANSACTIONAL)
        db_session.add(account)
        db_session.flush()
        return account.id

    pot, other = make("Onderhoud Auto"), make("Reservering Vakantie")

    ok = client.put(f"/api/gripr/accounts/{pot}", json={"held_in_account_id": account_id})
    assert ok.status_code == 200 and ok.json()["held_in_account_id"] == account_id
    assert client.put(f"/api/gripr/accounts/{other}", json={"held_in_account_id": pot}).status_code == 400  # no pot in a pot
    assert client.put(f"/api/gripr/accounts/{account_id}", json={"held_in_account_id": other}).status_code == 400  # it holds a pot
    assert client.put(f"/api/gripr/accounts/{pot}", json={"held_in_account_id": pot}).status_code == 400
    cleared = client.put(f"/api/gripr/accounts/{pot}", json={"held_in_account_id": None})
    assert cleared.json()["held_in_account_id"] is None


def test_trading212_is_an_api_key_bank_with_nothing_to_connect(client, db_session, banks, monkeypatch):
    from app.services.trading212_provider import trading212_provider

    t212 = BankConnection(aspsp_name="Trading 212", aspsp_country="NL", source_prefix="t212", provider="trading212")
    db_session.add(t212)
    db_session.flush()
    bank_sync_repo.upsert_account(db_session, "T212", connection_id=t212.id, product="Invest account")
    monkeypatch.setattr(trading212_provider, "api_key", "key")
    monkeypatch.setattr(trading212_provider, "api_secret", "secret")

    body = client.get("/api/gripr/banks").json()
    connection = body["connections"][-1]

    assert body["configured"] is True  # a Trading 212 key is enough, without Enable Banking
    assert (connection["kind"], connection["connected"], connection["accounts"][0]["in_consent"]) == ("api_key", True, True)
    assert body["connections"][0]["kind"] == "consent"
    assert client.post(f"/api/gripr/banks/{t212.id}/connect").status_code == 409
