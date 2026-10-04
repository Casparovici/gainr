from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.services.trading212_provider import (
    Trading212AuthError,
    Trading212Error,
    Trading212Provider,
    parse_cash_csv,
    parse_dividend,
    parse_fill,
)

INSTRUMENT_AMZN = {"ticker": "AMZN_US_EQ", "name": "Amazon", "isin": "US0231351067", "currency": "USD"}
INSTRUMENT_TDIV = {"ticker": "TDIVa_EQ", "name": "VanEck Dividend Leaders", "isin": "NL0011683594", "currency": "EUR"}


def order_item(fill_id=1, *, side="BUY", instrument=INSTRUMENT_AMZN, quantity=2.0, price=246.77, created="2026-09-28T15:35:43.000Z",
               net=434.74, wallet="EUR", fx=1.13695316, taxes=(-0.65,), origin="ANDROID", filled=True):
    order = {"id": fill_id * 10, "side": side, "status": "FILLED" if filled else "CANCELLED", "ticker": instrument["ticker"],
             "createdAt": created, "initiatedFrom": origin, "instrument": instrument}
    if not filled:
        return {"order": order}
    return {
        "order": order,
        "fill": {
            "id": fill_id, "quantity": quantity, "price": price, "type": "TRADE", "filledAt": created,
            "walletImpact": {"currency": wallet, "netValue": net, "fxRate": fx,
                             "taxes": [{"name": "CURRENCY_CONVERSION_FEE", "quantity": t, "currency": wallet} for t in taxes]},
        },
    }


def test_a_fill_paid_in_euros_keeps_its_net_value_fees_and_rate():
    fill = parse_fill(order_item())

    assert fill.side == "BUY"
    assert fill.instrument.isin == "US0231351067"
    assert (fill.quantity, fill.price, fill.net_value, fill.fees) == (Decimal("2.0"), Decimal("246.77"), Decimal("434.74"), Decimal("0.65"))
    assert fill.wallet_currency == "EUR"
    assert fill.fx_rate == Decimal("1.13695316")
    assert fill.filled_at == datetime(2026, 9, 28, 15, 35, 43, tzinfo=timezone.utc)
    assert not fill.auto_invest


def test_a_sell_arrives_negative_and_is_kept_positive():
    fill = parse_fill(order_item(side="SELL", quantity=-29.3916214, net=2239.94, wallet="USD", fx=1, taxes=()))

    assert fill.side == "SELL"
    assert fill.quantity == Decimal("29.3916214")
    assert fill.wallet_currency == "USD"


def test_an_auto_invest_buy_is_marked_and_a_cancelled_order_is_no_fill():
    assert parse_fill(order_item(origin="AUTOINVEST", instrument=INSTRUMENT_TDIV, taxes=())).auto_invest
    assert parse_fill(order_item(filled=False)) is None


def test_a_fill_without_a_usable_isin_or_price_is_skipped():
    assert parse_fill(order_item(instrument={**INSTRUMENT_AMZN, "isin": "nope"})) is None
    assert parse_fill(order_item(price=0)) is None
    assert parse_fill({"order": "garbage"}) is None


def test_a_dividend_is_parsed_in_euros():
    dividend = parse_dividend({
        "reference": "div-1", "instrument": INSTRUMENT_TDIV, "amountInEuro": 20.54, "paidOn": "2026-09-09T14:59:59.000+02:00",
    })

    assert dividend.amount_eur == Decimal("20.54")
    assert dividend.paid_at == datetime(2026, 9, 9, 12, 59, 59, tzinfo=timezone.utc)
    assert parse_dividend({"reference": "x", "instrument": INSTRUMENT_TDIV, "amountInEuro": "NaN", "paidOn": "2026-09-09T00:00:00Z"}) is None


CSV = """Action,Time (UTC),ISIN,Ticker,Name,Notes,ID,No. of shares,Price / share,Currency (Price / share),Exchange rate,Total,Currency (Total),Merchant name,Merchant category
Card debit,2026-10-02 10:12:51+00:00,,,,,c-1,,,,,-15.99,EUR,Netflix,UTILITIES
Spending cashback,2026-10-02 10:13:00+00:00,,,,,c-2,,,,,0.11,EUR,,
Interest on cash,2026-10-02 01:04:32+00:00,,,,,c-3,,,,,0.03,USD,,
Market buy,2026-10-02 14:23:06+00:00,US58733R1023,MELI,MercadoLibre,,EOF1,0.2,1698.22,USD,1.13,-301.62,EUR,,
Deposit,2026-10-01 05:49:36+00:00,,,,Transaction ID: X,c-4,,,,,500.00,EUR,,
Card debit,2026-09-30 22:30:00+00:00,,,,,c-5,,,,,-8.00,EUR,Albert Heijn,RETAIL_STORES
Card debit,not a time,,,,,c-6,,,,,-1.00,EUR,Lidl,RETAIL_STORES
"""


def test_the_export_keeps_cash_rows_and_leaves_trades_to_the_orders_endpoint():
    entries = parse_cash_csv(CSV)

    assert [e.entry_id for e in entries] == ["c-1", "c-2", "c-3", "c-4", "c-5"]
    netflix = entries[0]
    assert (netflix.action, netflix.amount, netflix.merchant, netflix.merchant_category) == ("Card debit", Decimal("-15.99"), "Netflix", "UTILITIES")
    assert entries[2].currency == "USD"


def test_a_card_payment_late_in_the_evening_belongs_to_the_amsterdam_day():
    late = parse_cash_csv(CSV)[4]

    assert late.at.date() == date(2026, 9, 30)
    assert late.local_date == date(2026, 10, 1)  # 00:30 in Amsterdam


# -- the client ----------------------------------------------------------------------------------


def client(handler, sleeps: list | None = None) -> Trading212Provider:
    recorded = sleeps if sleeps is not None else []
    return Trading212Provider(api_key="key", api_secret="secret", transport=httpx.MockTransport(handler), sleep=recorded.append)


def test_fills_page_back_until_the_start_date_and_no_further():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.headers["authorization"].startswith("Basic ")
        if "cursor" not in str(request.url):
            return httpx.Response(200, json={
                "items": [order_item(3, created="2026-10-02T10:00:00Z"), order_item(2, created="2026-10-01T10:00:00Z")],
                "nextPagePath": "/api/v0/equity/history/orders?cursor=2&limit=50",
            })
        return httpx.Response(200, json={
            "items": [order_item(1, created="2026-09-30T10:00:00Z")],
            "nextPagePath": "/api/v0/equity/history/orders?cursor=1&limit=50",
        })

    fills = client(handler).fills_since(date(2026, 10, 1))

    assert [f.fill_id for f in fills] == ["3", "2"]
    assert len(calls) == 2  # the second page reached before the start date; no third


def test_a_next_page_outside_the_api_is_never_followed():
    def handler(request):
        return httpx.Response(200, json={"items": [order_item(1, created="2026-10-02T10:00:00Z")], "nextPagePath": "https://evil.example/x"})

    with pytest.raises(Trading212Error):
        client(handler).fills_since(date(2026, 10, 1))


def test_a_refused_key_is_an_auth_error():
    with pytest.raises(Trading212AuthError):
        client(lambda r: httpx.Response(403)).dividends_since(date(2026, 10, 1))


def test_a_rate_limit_is_waited_out_then_retried():
    answers = [httpx.Response(429, headers={"retry-after": "5"}), httpx.Response(200, json={"items": []})]
    sleeps: list = []

    dividends = client(lambda r: answers.pop(0), sleeps).dividends_since(date(2026, 10, 1))

    assert dividends == []
    assert sleeps == [5.0]


def test_the_export_is_requested_polled_and_downloaded_without_the_credentials():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "exports.example":
            seen["download_auth"] = request.headers.get("authorization")
            return httpx.Response(200, text=CSV)
        if request.method == "POST":
            seen["body"] = request.content
            return httpx.Response(200, json={"reportId": 7})
        return httpx.Response(200, json=[{"reportId": 7, "status": "Finished", "downloadLink": "https://exports.example/r.csv"}])

    entries = client(handler).cash_activity(date(2026, 10, 1), until=datetime(2026, 10, 2, 20, tzinfo=timezone.utc))

    assert seen["download_auth"] is None
    assert b'"timeFrom":"2026-09-30T22:00:00Z"' in seen["body"]  # midnight in Amsterdam
    assert [e.entry_id for e in entries] == ["c-1", "c-2", "c-3", "c-4", "c-5"]


def test_an_export_link_that_isnt_https_is_refused():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"reportId": 7})
        return httpx.Response(200, json=[{"reportId": 7, "status": "Finished", "downloadLink": "file:///etc/passwd"}])

    with pytest.raises(Trading212Error):
        client(handler).cash_activity(date(2026, 10, 1))


def test_without_a_key_nothing_is_requested():
    provider = Trading212Provider(api_key="", api_secret="", transport=httpx.MockTransport(lambda r: pytest.fail("called")))

    assert not provider.configured
    with pytest.raises(Trading212Error):
        provider.fills_since(date(2026, 10, 1))
