"""Covers the logo endpoint's caching contract.

An earlier version served logos with a day-long expiry and no validator, which meant a
browser that had seen a logo would not ask again for 24 hours — so improving the image
changed nothing on screen. These pin the revalidation that replaced it.
"""

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.models.asset_logo import AssetLogo
from app.routers import assets as assets_router
from app.services.price_provider import SymbolMatch
from app.services.price_service import price_service

PNG = b"\x89PNG\r\n\x1a\n-pretend-image-bytes"


class FakeMarket:
    """Stands in for Yahoo: what a symbol search finds, and the currency each listing quotes in."""

    def __init__(self):
        self.listings = {
            "TDIV": SymbolMatch("TDIV", "First Trust NASDAQ Technology Dividend Index Fund", "NASDAQ", "ETF"),
            "TDIV.AS": SymbolMatch("TDIV.AS", "VanEck Morningstar Developed Markets Dividend Leaders UCITS ETF", "Amsterdam", "ETF"),
            "IQQW.DE": SymbolMatch("IQQW.DE", "iShares MSCI World UCITS ETF USD (Dist)", "XETRA", "ETF"),
            "WISE.L": SymbolMatch("WISE.L", "Wise plc", "London", "Equity"),
        }
        self.currencies = {"TDIV": "USD", "TDIV.AS": "EUR", "IQQW.DE": "EUR", "WISE.L": "GBp"}

    def search(self, query):
        return [m for symbol, m in self.listings.items() if symbol.split(".")[0] == query.upper().split(".")[0]]

    def get_currency(self, symbol):
        return self.currencies.get(symbol)


@pytest.fixture(autouse=True)
def market(monkeypatch):
    fake = FakeMarket()
    monkeypatch.setattr(price_service, "provider", fake)
    return fake


@pytest.fixture()
def client(db_session):
    # Only the router under test, rather than app.main — importing that would run
    # create_all against the real portfolio.db.
    app = FastAPI()
    app.include_router(assets_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def asset_with_logo(db_session):
    asset = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    db_session.add(
        AssetLogo(asset_id=asset.id, content_type="image/png", image=PNG, source_url="https://acme.com/icon.png")
    )
    db_session.commit()
    return asset


def test_a_logo_is_served_with_a_validator_the_browser_can_check(client, asset_with_logo):
    response = client.get(f"/api/assets/{asset_with_logo.id}/logo")

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["etag"]
    # An expiry alone would let a stale copy sit unquestioned for as long as it lasts.
    assert "no-cache" in response.headers["cache-control"]


def test_an_unchanged_logo_costs_a_304_and_no_bytes(client, asset_with_logo):
    etag = client.get(f"/api/assets/{asset_with_logo.id}/logo").headers["etag"]

    response = client.get(f"/api/assets/{asset_with_logo.id}/logo", headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.content == b""


def test_a_changed_logo_is_sent_in_full_to_a_browser_holding_the_old_one(client, asset_with_logo, db_session):
    stale = client.get(f"/api/assets/{asset_with_logo.id}/logo").headers["etag"]

    # what re-resolving to a better source looks like
    logo = db_session.get(AssetLogo, asset_with_logo.id)
    logo.image = PNG + b"-but-bigger-and-sharper"
    db_session.commit()

    response = client.get(f"/api/assets/{asset_with_logo.id}/logo", headers={"If-None-Match": stale})

    assert response.status_code == 200
    assert response.content == logo.image
    assert response.headers["etag"] != stale


def test_a_holding_with_no_logo_is_a_plain_404(client, db_session):
    # No yahoo_symbol, so nothing is looked up and the answer is immediate.
    asset = Asset(ticker="MYSTERY", name="Mystery", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.commit()

    response = client.get(f"/api/assets/{asset.id}/logo")

    assert response.status_code == 404
    assert response.content == b""


def test_an_unknown_asset_is_a_404(client):
    assert client.get("/api/assets/9999/logo").status_code == 404


# -- creating an asset -------------------------------------------------------


def test_creating_an_asset_applies_defaults(client):
    response = client.post("/api/assets", json={"ticker": "NEWCO", "name": "New Co"})

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "NEWCO"
    assert body["name"] == "New Co"
    assert body["asset_class"] == "equity"
    assert body["native_currency"] == "EUR"
    assert body["yahoo_symbol"] == "NEWCO"  # defaults to the ticker when omitted


def test_creating_an_asset_with_an_existing_ticker_returns_that_asset(client):
    first = client.post("/api/assets", json={"ticker": "NEWCO", "name": "New Co"}).json()

    second = client.post("/api/assets", json={"ticker": "NEWCO", "name": "Something Else"})

    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert second.json()["name"] == "New Co"  # the original row, unchanged


def test_a_new_asset_takes_its_currency_from_its_listing(client):
    body = client.post("/api/assets", json={"ticker": "WISE", "name": "Wise", "yahoo_symbol": "WISE.L"}).json()

    # London quotes in pence: the asset is GBP with prices scaled down 100x, not a 100x overvaluation.
    assert (body["native_currency"], body["yahoo_symbol"]) == ("GBP", "WISE.L")


def test_lookup_shows_every_listing_with_the_exact_one_first(client):
    body = client.get("/api/assets/lookup", params={"q": "tdiv"}).json()

    assert body["exact"] is True
    assert [m["symbol"] for m in body["matches"]] == ["TDIV", "TDIV.AS"]
    assert body["matches"][0]["name"].startswith("First Trust")  # plain TDIV isn't the VanEck fund


def test_lookup_for_a_ticker_yahoo_only_knows_with_a_suffix(client):
    body = client.get("/api/assets/lookup", params={"q": "IQQW"}).json()

    assert body["exact"] is False
    assert [(m["symbol"], m["exchange"]) for m in body["matches"]] == [("IQQW.DE", "XETRA")]


def test_lookup_rejects_odd_input(client):
    assert client.get("/api/assets/lookup", params={"q": ""}).status_code == 422
    assert client.get("/api/assets/lookup", params={"q": "x" * 41}).status_code == 422
    assert client.get("/api/assets/lookup", params={"q": "<script>"}).status_code == 422


def test_creating_an_asset_rejects_blank_ticker_or_name(client):
    assert client.post("/api/assets", json={"ticker": "  ", "name": "New Co"}).status_code == 422
    assert client.post("/api/assets", json={"ticker": "NEWCO", "name": ""}).status_code == 422


# -- target weight ------------------------------------------------------------


def test_updating_target_weight_through_the_router_persists_it(client, db_session, portfolio_id):
    asset = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.commit()

    response = client.put(
        f"/api/assets/{asset.id}/target-weight", json={"portfolio_id": portfolio_id, "target_weight_pct": "25.5"}
    )

    assert response.status_code == 200
    assert Decimal(response.json()["target_weight_pct"]) == Decimal("25.5")


def test_updating_target_weight_past_100_percent_is_a_400(client, db_session, portfolio_id):
    a = Asset(ticker="A", name="A Inc", asset_class="equity", native_currency="EUR")
    b = Asset(ticker="B", name="B Inc", asset_class="equity", native_currency="EUR")
    db_session.add_all([a, b])
    db_session.commit()
    client.put(f"/api/assets/{a.id}/target-weight", json={"portfolio_id": portfolio_id, "target_weight_pct": "70"})

    response = client.put(f"/api/assets/{b.id}/target-weight", json={"portfolio_id": portfolio_id, "target_weight_pct": "40"})

    assert response.status_code == 400
    assert "110" in response.json()["detail"]


def test_target_weight_in_one_portfolio_does_not_count_against_another(client, db_session, portfolio_id):
    from app.models.portfolio import Portfolio

    other = Portfolio(name="Other Portfolio")
    db_session.add(other)
    a = Asset(ticker="A", name="A Inc", asset_class="equity", native_currency="EUR")
    db_session.add(a)
    db_session.commit()
    client.put(f"/api/assets/{a.id}/target-weight", json={"portfolio_id": portfolio_id, "target_weight_pct": "70"})

    response = client.put(f"/api/assets/{a.id}/target-weight", json={"portfolio_id": other.id, "target_weight_pct": "70"})

    assert response.status_code == 200


# -- DLT rating ---------------------------------------------------------------


def test_updating_dlt_judgment_through_the_router_persists_it(client, db_session):
    asset = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.commit()

    response = client.put(f"/api/assets/{asset.id}", json={"dlt_judgment": "attractive"})

    assert response.status_code == 200
    assert response.json()["dlt_judgment"] == "attractive"


def test_clearing_dlt_judgment_sets_it_back_to_no_coverage(client, db_session):
    from app.models.asset import DltJudgment

    asset = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR", dlt_judgment=DltJudgment.ATTRACTIVE)
    db_session.add(asset)
    db_session.commit()

    response = client.put(f"/api/assets/{asset.id}", json={"dlt_judgment": None})

    assert response.status_code == 200
    assert response.json()["dlt_judgment"] is None
    db_session.refresh(asset)
    assert asset.dlt_judgment is None


# -- transactions for one position ------------------------------------------


def test_transactions_can_be_listed_for_a_single_asset(db_session, portfolio_id):
    """The position card asks by asset id, not by ticker — a ticker is an editable label."""
    from datetime import date

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.models.transaction import Transaction, TransactionType
    from app.routers import transactions as transactions_router

    held = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    other = Asset(ticker="OTHER", name="Other", asset_class="equity", native_currency="EUR")
    db_session.add_all([held, other])
    db_session.flush()

    for asset, count in ((held, 2), (other, 3)):
        for index in range(count):
            db_session.add(
                Transaction(
                    portfolio_id=portfolio_id, asset_id=asset.id, date=date(2024, 1, index + 1), type=TransactionType.BUY,
                    quantity=Decimal(1), value_eur=Decimal(10), costs=Decimal(0), total_eur=Decimal(10),
                )
            )
    # a cash movement, which belongs to no asset at all
    db_session.add(
        Transaction(portfolio_id=portfolio_id, asset_id=None, date=date(2024, 2, 1), type=TransactionType.DEPOSIT,
                    value_eur=Decimal(500), costs=Decimal(0), total_eur=Decimal(500))
    )
    db_session.commit()

    app = FastAPI()
    app.include_router(transactions_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    page = client.get("/api/transactions", params={"portfolio_id": portfolio_id, "asset_id": held.id}).json()

    assert page["total"] == 2
    assert {item["asset_id"] for item in page["items"]} == {held.id}
    # and without the filter everything is still there
    assert client.get("/api/transactions", params={"portfolio_id": portfolio_id}).json()["total"] == 6


def test_transactions_export_csv_covers_every_transaction_with_the_asset_resolved(db_session, portfolio_id):
    from datetime import date

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.models.transaction import Transaction, TransactionType
    from app.routers import transactions as transactions_router

    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="USD")
    db_session.add(asset)
    db_session.flush()
    db_session.add(
        Transaction(
            portfolio_id=portfolio_id, asset_id=asset.id, date=date(2024, 3, 1), type=TransactionType.BUY,
            quantity=Decimal("2"), price=Decimal("100"), value_eur=Decimal("200"),
            costs=Decimal("1"), total_eur=Decimal("201"), broker="Trading212",
        )
    )
    # a cash movement, which belongs to no asset — the export must not choke on it
    db_session.add(
        Transaction(portfolio_id=portfolio_id, asset_id=None, date=date(2024, 2, 1), type=TransactionType.DEPOSIT,
                    value_eur=Decimal(500), costs=Decimal(0), total_eur=Decimal(500))
    )
    db_session.commit()

    app = FastAPI()
    app.include_router(transactions_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/transactions/export.csv", params={"portfolio_id": portfolio_id})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = response.text.strip().splitlines()
    assert rows[0] == "date,type,ticker,asset_name,quantity,price,native_currency,local_value,fx_rate,value_eur,costs,total_eur,broker,to_broker,notes"
    assert len(rows) == 3  # header + the two transactions above
    # list_all_transactions orders by date, so the February deposit comes first.
    assert rows[1].startswith("2024-02-01,Deposit,,,")
    assert rows[2].startswith("2024-03-01,Buy,ACME,Acme,2.00000000,100.00000000,USD")


def test_a_transfer_moves_cash_between_brokers_without_an_asset(db_session, portfolio_id):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import transactions as transactions_router

    app = FastAPI()
    app.include_router(transactions_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.post(
        "/api/transactions",
        json={
            "date": "2024-05-01",
            "type": "Transfer",
            "portfolio_id": portfolio_id,
            "total_eur": "500",
            "broker": "DEGIRO",
            "to_broker": "IBKR",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] is None
    assert body["broker"] == "DEGIRO"
    assert body["to_broker"] == "IBKR"
    assert Decimal(body["total_eur"]) == Decimal(500)

    listed = client.get("/api/transactions", params={"portfolio_id": portfolio_id, "type": "Transfer"}).json()
    assert listed["total"] == 1
    assert listed["items"][0]["to_broker"] == "IBKR"


# -- position notes -----------------------------------------------------------------------------


def test_notes_are_created_and_listed_newest_first(client, db_session):
    asset = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.commit()

    first = client.post(f"/api/assets/{asset.id}/notes", json={"title": "First", "body": "Bought the dip"})
    second = client.post(f"/api/assets/{asset.id}/notes", json={"title": "Second", "body": "**Earnings** beat"})
    assert first.status_code == 200 and second.status_code == 200

    response = client.get(f"/api/assets/{asset.id}/notes")
    assert response.status_code == 200
    titles = [n["title"] for n in response.json()]
    assert titles == ["Second", "First"]  # newest first


def test_a_note_can_be_edited_and_deleted(client, db_session):
    asset = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.commit()
    note_id = client.post(f"/api/assets/{asset.id}/notes", json={"title": "Draft", "body": "..."}).json()["id"]

    updated = client.put(f"/api/assets/{asset.id}/notes/{note_id}", json={"body": "Final thoughts"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Draft"  # untouched field survives a partial update
    assert updated.json()["body"] == "Final thoughts"

    deleted = client.delete(f"/api/assets/{asset.id}/notes/{note_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/assets/{asset.id}/notes").json() == []


def test_a_note_timestamp_is_serialized_with_an_explicit_utc_offset(client, db_session):
    # SQLite's CURRENT_TIMESTAMP comes back as a naive datetime with no timezone marker of its
    # own, even though the value is UTC. Serialized bare, `new Date(iso)` on the frontend reads
    # it as local time, silently shifting "just now" by the browser's UTC offset.
    asset = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.commit()

    response = client.post(f"/api/assets/{asset.id}/notes", json={"title": "T", "body": "B"})
    created_at = response.json()["created_at"]
    assert created_at.endswith("+00:00") or created_at.endswith("Z")


def test_a_note_under_the_wrong_asset_is_a_404(client, db_session):
    a = Asset(ticker="AAA", name="A", asset_class="equity", native_currency="EUR")
    b = Asset(ticker="BBB", name="B", asset_class="equity", native_currency="EUR")
    db_session.add_all([a, b])
    db_session.commit()
    note_id = client.post(f"/api/assets/{a.id}/notes", json={"title": "T", "body": "B"}).json()["id"]

    response = client.put(f"/api/assets/{b.id}/notes/{note_id}", json={"title": "Hijacked"})
    assert response.status_code == 404
