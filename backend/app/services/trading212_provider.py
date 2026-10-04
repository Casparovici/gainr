"""Client for Trading 212's public API (https://docs.trading212.com/api) -- read-only: order fills,
dividends, and the account's cash activity (card payments, deposits, interest, cashback), nothing
that could place an order. See docs/adr/0031-trading212-sync.md.

One Trading 212 Invest account holds both the reader's investments and the cash their debit card
spends, so both gripr (the card, as the T212 Debit account) and gainr (the fills) read from here.

- Fills come from `/equity/history/orders` and dividends from `/equity/history/dividends`, newest
  first, paged by `nextPagePath`.
- Cash activity comes from the CSV export: the JSON `/history/transactions` only says `WITHDRAW`
  for a card payment, while the export names the merchant. An export is asynchronous -- requested,
  then polled until Trading 212 has written it -- and listing exports is limited to about one call
  a minute, so reading it takes a minute or two.

Authentication is HTTP Basic with a key/secret pair from the server's environment. The key is
generated read-only and restricted to the server's IP in the Trading 212 app; Trading 212 answers
401/403 when it's wrong or the IP has changed.

Everything that comes back is untrusted input: amounts are parsed as Decimal and must be finite,
text is trimmed and length-capped, anything that doesn't fit is skipped rather than half-imported,
and the only URLs ever followed are Trading 212's own pagination paths and an https export link
(fetched without the credentials).
"""

import csv
import io
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from app import config

BASE_URL = "https://live.trading212.com"
API_PREFIX = "/api/v0/"
TIMEOUT = 30.0
PAGE_LIMIT = 50
# Hard stop for pagination -- far above a personal account's activity in any sync window, only
# there so an API that keeps handing out a next page can't loop forever.
MAX_PAGES = 40
# A 429 is waited out (Trading 212 says when the window resets) at most this long, this often.
MAX_RATE_LIMIT_WAIT = 70.0
MAX_RETRIES = 4
# An export usually takes under a minute; listing exports is itself limited to about one call a
# minute.
EXPORT_POLL_SECONDS = 20.0
EXPORT_TIMEOUT_SECONDS = 300.0
TEXT_LIMIT = 120

# Trading 212 stamps everything in UTC; the reader's day is Amsterdam's, so a card payment at
# 00:30 belongs to the day it was made.
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")


class Trading212Error(Exception):
    """Trading 212 couldn't be reached or answered with something unusable."""


class Trading212AuthError(Trading212Error):
    """The API key was refused: wrong, revoked, missing a permission, or used from an IP the key
    isn't allowed from (the home connection's address changed). Retrying won't help."""


@dataclass(frozen=True)
class Instrument:
    isin: str
    ticker: str  # Trading 212's own, e.g. "AMZN_US_EQ"
    name: str
    currency: str


@dataclass(frozen=True)
class Fill:
    fill_id: str
    side: str  # "BUY" | "SELL"
    instrument: Instrument
    quantity: Decimal  # always positive
    price: Decimal  # per share, in the instrument's currency
    filled_at: datetime  # UTC
    # The cash the fill moved: in the account currency (EUR) or, for a trade paid from the USD
    # wallet, in USD. Fees are already inside net_value.
    wallet_currency: str
    net_value: Decimal
    # Units of the instrument's currency per unit of the wallet's (1.137 USD per EUR), or None.
    fx_rate: Decimal | None
    fees: Decimal  # positive, in the wallet currency
    auto_invest: bool


@dataclass(frozen=True)
class Dividend:
    reference: str
    instrument: Instrument
    amount_eur: Decimal
    paid_at: datetime  # UTC


@dataclass(frozen=True)
class CashEntry:
    """One row of the CSV export that isn't a trade: "Card debit", "Deposit", "Withdrawal",
    "Interest on cash", "Spending cashback", "Currency conversion", ..."""

    entry_id: str
    action: str
    at: datetime  # UTC
    amount: Decimal  # signed: negative is money out
    currency: str
    merchant: str
    merchant_category: str

    @property
    def local_date(self) -> date:
        return local_date(self.at)


def local_date(moment: datetime) -> date:
    return moment.astimezone(LOCAL_TZ).date()


# -- parsing -------------------------------------------------------------------------------------


def _text(value: object, limit: int = TEXT_LIMIT) -> str:
    return str(value).strip()[:limit] if value is not None else ""


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _moment(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _instrument(raw: object) -> Instrument | None:
    if not isinstance(raw, dict):
        return None
    isin = _text(raw.get("isin"), 12).upper()
    if len(isin) != 12 or not isin.isalnum():
        return None
    return Instrument(
        isin=isin,
        ticker=_text(raw.get("ticker"), 32),
        name=_text(raw.get("name")),
        currency=_text(raw.get("currency"), 8).upper(),
    )


def parse_fill(item: object) -> Fill | None:
    """One `/equity/history/orders` item as a fill, or None for an order that didn't fill (a
    cancelled one has no `fill`) or doesn't parse."""
    if not isinstance(item, dict):
        return None
    order, fill = item.get("order"), item.get("fill")
    if not isinstance(order, dict) or not isinstance(fill, dict):
        return None
    instrument = _instrument(order.get("instrument"))
    side = _text(order.get("side"), 8).upper()
    quantity = _decimal(fill.get("quantity"))
    price = _decimal(fill.get("price"))
    filled_at = _moment(fill.get("filledAt"))
    wallet = fill.get("walletImpact") if isinstance(fill.get("walletImpact"), dict) else {}
    net_value = _decimal(wallet.get("netValue"))
    if (
        instrument is None or side not in ("BUY", "SELL") or quantity is None or quantity == 0
        or price is None or price <= 0 or filled_at is None or net_value is None or fill.get("id") is None
    ):
        return None
    wallet_currency = _text(wallet.get("currency"), 8).upper()
    fees = Decimal(0)
    for tax in wallet.get("taxes") or []:
        amount = _decimal(tax.get("quantity")) if isinstance(tax, dict) else None
        if amount is not None and _text(tax.get("currency"), 8).upper() in ("", wallet_currency):
            fees += abs(amount)
    fx_rate = _decimal(wallet.get("fxRate"))
    return Fill(
        fill_id=_text(fill.get("id"), 40),
        side=side,
        instrument=instrument,
        quantity=abs(quantity),
        price=price,
        filled_at=filled_at.astimezone(timezone.utc),
        wallet_currency=wallet_currency,
        net_value=abs(net_value),
        fx_rate=fx_rate if fx_rate is not None and fx_rate > 0 else None,
        fees=fees,
        auto_invest=_text(order.get("initiatedFrom"), 20).upper() == "AUTOINVEST",
    )


def parse_dividend(item: object) -> Dividend | None:
    if not isinstance(item, dict):
        return None
    instrument = _instrument(item.get("instrument"))
    amount = _decimal(item.get("amountInEuro"))
    paid_at = _moment(item.get("paidOn"))
    reference = _text(item.get("reference"), 60)
    if instrument is None or amount is None or paid_at is None or not reference:
        return None
    return Dividend(reference=reference, instrument=instrument, amount_eur=amount, paid_at=paid_at.astimezone(timezone.utc))


def parse_cash_csv(text: str) -> list[CashEntry]:
    """The export's non-trade rows. Trades ("Market buy", "Limit sell", ...) and dividends come
    from the JSON endpoints instead, with their fill ids and ISINs."""
    entries: list[CashEntry] = []
    for row in csv.DictReader(io.StringIO(text)):
        action = _text(row.get("Action"), 40)
        if not action or action.lower().startswith(("market ", "limit ", "stop ")) or action.lower().startswith("dividend"):
            continue
        entry_id = _text(row.get("ID"), 60)
        at = _moment((row.get("Time (UTC)") or row.get("Time") or "").replace(" ", "T", 1))
        amount = _decimal(row.get("Total"))
        if not entry_id or at is None or amount is None:
            continue
        entries.append(
            CashEntry(
                entry_id=entry_id,
                action=action,
                at=at.astimezone(timezone.utc),
                amount=amount,
                currency=_text(row.get("Currency (Total)"), 8).upper(),
                merchant=_text(row.get("Merchant name")),
                merchant_category=_text(row.get("Merchant category"), 40),
            )
        )
    return entries


# -- the client ----------------------------------------------------------------------------------


class Trading212Provider:
    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.api_key = api_key if api_key is not None else config.T212_API_KEY
        self.api_secret = api_secret if api_secret is not None else config.T212_API_SECRET
        self._transport = transport
        self._sleep = sleep

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _client(self) -> httpx.Client:
        if not self.configured:
            raise Trading212Error("Trading 212 isn't configured on this server")
        return httpx.Client(
            base_url=BASE_URL, auth=(self.api_key, self.api_secret), timeout=TIMEOUT, transport=self._transport
        )

    def _get(self, client: httpx.Client, path: str, **kwargs) -> object:
        return self._request(client, "GET", path, **kwargs)

    def _request(self, client: httpx.Client, method: str, path: str, **kwargs) -> object:
        if not path.startswith(API_PREFIX):
            raise Trading212Error("Trading 212 pointed outside its API")
        for _ in range(MAX_RETRIES):
            try:
                response = client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                raise Trading212Error(f"Couldn't reach Trading 212 ({type(exc).__name__})") from exc
            if response.status_code in (401, 403):
                raise Trading212AuthError("Trading 212 refused the API key")
            if response.status_code == 429:
                self._sleep(self._rate_limit_wait(response))
                continue
            if response.status_code >= 400:
                raise Trading212Error(f"Trading 212 answered {response.status_code}")
            try:
                return response.json()
            except ValueError as exc:
                raise Trading212Error("Trading 212 sent something that isn't JSON") from exc
        raise Trading212Error("Trading 212 kept rate-limiting the request")

    @staticmethod
    def _rate_limit_wait(response: httpx.Response) -> float:
        reset = _decimal(response.headers.get("x-ratelimit-reset"))
        if reset is not None:
            wait = float(reset) - time.time()
        else:
            wait = float(_decimal(response.headers.get("retry-after")) or 60)
        return min(max(wait, 1.0), MAX_RATE_LIMIT_WAIT)

    def _paged(self, client: httpx.Client, path: str, stop: Callable[[list], bool]) -> list:
        items: list = []
        next_path: str | None = f"{API_PREFIX}{path}?limit={PAGE_LIMIT}"
        for _ in range(MAX_PAGES):
            if not next_path:
                break
            page = self._get(client, next_path)
            batch = page.get("items") if isinstance(page, dict) else None
            if not isinstance(batch, list):
                raise Trading212Error("Trading 212 sent a page without items")
            items.extend(batch)
            if not batch or stop(batch):
                break
            next_path = page.get("nextPagePath") if isinstance(page.get("nextPagePath"), str) else None
        return items

    def fills_since(self, since: date) -> list[Fill]:
        """Every fill on or after `since` (in the reader's own time zone), newest first."""
        def older(batch: list) -> bool:
            moments = [_moment((i.get("order") or {}).get("createdAt")) for i in batch if isinstance(i, dict)]
            return any(m is not None and local_date(m) < since for m in moments)

        with self._client() as client:
            raw = self._paged(client, "equity/history/orders", older)
        fills = [f for f in (parse_fill(i) for i in raw) if f is not None]
        return [f for f in fills if local_date(f.filled_at) >= since]

    def dividends_since(self, since: date) -> list[Dividend]:
        def older(batch: list) -> bool:
            moments = [_moment(i.get("paidOn")) for i in batch if isinstance(i, dict)]
            return any(m is not None and local_date(m) < since for m in moments)

        with self._client() as client:
            raw = self._paged(client, "equity/history/dividends", older)
        dividends = [d for d in (parse_dividend(i) for i in raw) if d is not None]
        return [d for d in dividends if local_date(d.paid_at) >= since]

    def cash_activity(self, since: date, until: datetime | None = None) -> list[CashEntry]:
        """Card payments, deposits, withdrawals, interest and cashback from `since` on, through
        the CSV export. Takes a minute or two: Trading 212 writes the export in the background."""
        until = until or datetime.now(timezone.utc)
        start = datetime.combine(since, datetime.min.time(), LOCAL_TZ).astimezone(timezone.utc)
        body = {
            "dataIncluded": {"includeDividends": False, "includeInterest": True, "includeOrders": False, "includeTransactions": True},
            "timeFrom": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeTo": until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        with self._client() as client:
            requested = self._request(client, "POST", f"{API_PREFIX}equity/history/exports", json=body)
            report_id = requested.get("reportId") if isinstance(requested, dict) else None
            if report_id is None:
                raise Trading212Error("Trading 212 didn't start the export")
            link = self._wait_for_export(client, report_id)
        if urlparse(link).scheme != "https":
            raise Trading212Error("Trading 212's export link isn't https")
        try:
            # A pre-signed link to Trading 212's storage: fetched without the API credentials.
            with httpx.Client(timeout=TIMEOUT, transport=self._transport) as download:
                response = download.get(link)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise Trading212Error(f"Couldn't download the Trading 212 export ({type(exc).__name__})") from exc
        entries = parse_cash_csv(response.text)
        return [e for e in entries if e.local_date >= since]

    def _wait_for_export(self, client: httpx.Client, report_id: object) -> str:
        waited = 0.0
        while waited < EXPORT_TIMEOUT_SECONDS:
            self._sleep(EXPORT_POLL_SECONDS)
            waited += EXPORT_POLL_SECONDS
            reports = self._get(client, f"{API_PREFIX}equity/history/exports")
            report = next(
                (r for r in reports if isinstance(r, dict) and r.get("reportId") == report_id), None
            ) if isinstance(reports, list) else None
            if report is None:
                continue
            status = _text(report.get("status"), 20)
            if status == "Finished" and isinstance(report.get("downloadLink"), str):
                return report["downloadLink"]
            if status in ("Failed", "Canceled", "Cancelled"):
                raise Trading212Error("Trading 212 couldn't write the export")
        raise Trading212Error("Trading 212's export wasn't ready in time")


trading212_provider = Trading212Provider()
