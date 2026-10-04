"""Client for Enable Banking (https://enablebanking.com), the licensed PSD2 account-information
aggregator gripr reads ING transactions through -- read-only: it starts a consent, turns the
code ING hands back into a session, and lists an account's booked transactions, nothing else.
See docs/adr/0029-ing-transactions-into-gripr.md.

Every call carries a JWT signed (RS256) with the app's own private key, which never leaves the
server; the bank login itself happens at ING, so no bank credentials ever pass through here.

Bank data is treated as untrusted input: amounts are parsed as Decimal and must be positive and
finite, text is trimmed and length-capped, and anything that doesn't fit is skipped rather than
half-imported -- what reaches ing_sync_service is always plain, bounded data.
"""

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
import jwt

from app import config

BASE_URL = "https://api.enablebanking.com"
TIMEOUT = 30.0
# The JWT only has to outlive one sync run; Enable Banking accepts up to 24h.
TOKEN_TTL_SECONDS = 3600
# Hard stop for pagination, far above a personal account's transactions in any sync window --
# only there so a misbehaving API that keeps returning a continuation key can't loop us forever.
MAX_PAGES = 50
NOTES_LIMIT = 500

# ING's remittance lines are "Key: value" pairs, a long value wrapping onto following lines
# without a key. Only these keys start a new field -- a wrapped line that happens to contain a
# colon ("http://...") stays part of the field before it.
_REMITTANCE_KEYS = (
    "Naam", "Omschrijving", "IBAN", "Kenmerk", "Machtiging ID", "Incassant ID", "Datum/Tijd",
    "Overige partij", "Valutadatum",
)
_KEY_LINE = re.compile(r"^(" + "|".join(re.escape(k) for k in _REMITTANCE_KEYS) + r"):\s?(.*)$")


class EnableBankingError(Exception):
    """Enable Banking couldn't be reached, rejected the app itself (wrong key, app inactive), or
    answered with something that isn't a usable response."""


class EnableBankingRateLimitError(EnableBankingError):
    """The bank refused the read for now: PSD2 lets it allow only a few reads a day without the
    reader present (Trade Republic answers ASPSP_RATE_LIMIT_EXCEEDED). Retrying sooner makes it worse."""


class EnableBankingSessionError(EnableBankingError):
    """The bank consent behind the session has expired, been revoked or closed -- the reader has
    to reconnect; retrying won't help."""


@dataclass
class BankAccount:
    # Enable Banking's id for this account *within this session* -- a new consent gives the same
    # IBAN a new uid, so the IBAN is what gripr keys accounts on.
    uid: str
    iban: str
    product: str
    holder_name: str
    currency: str


@dataclass
class BankSession:
    session_id: str
    valid_until: datetime
    accounts: list[BankAccount]


@dataclass
class BankTransaction:
    # The bank's own entry reference (ING), or one derived from the entry when the bank sends none
    # (Trade Republic) -- stable across fetches either way, which is what makes a sync idempotent.
    reference: str
    amount: Decimal  # always positive; direction comes from `is_debit`
    currency: str
    is_debit: bool
    booked_on: date
    transacted_on: date
    counterparty_name: str
    counterparty_iban: str | None
    description: str
    # How ING labels the payment: "Incasso", "iDEAL | Wero", "Online bankieren", ...
    method: str
    # Every remittance line joined, for matching rules that look for a savings account number.
    raw_text: str
    # The bank says nothing about who's on the other side -- a Trading 212 top-up or withdrawal.
    # Like an amount-only bank's entries, it can only be checked against a row already there (the
    # other bank's half of the transfer, once that's in), so it waits a couple of days first.
    anonymous: bool = False
    # The merchant of a card payment, when the bank names it (Trading 212) -- what a new payment's
    # category is learned from. ING's counterparty is in counterparty_name instead.
    merchant: str = ""


def _text(value: object, limit: int = 200) -> str:
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


def _iban(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    iban = _text(value.get("iban"), 34).replace(" ", "").upper()
    return iban or None


def _date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _amount(value: object) -> Decimal | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    # Direction comes from the credit/debit indicator; some banks (Trade Republic) also sign the
    # amount itself, so only its size is kept.
    if not amount.is_finite() or amount == 0:
        return None
    return abs(amount).quantize(Decimal("0.01"))


def describe(lines: list[str], counterparty_name: str) -> str:
    """The human part of ING's remittance lines: the "Omschrijving" (with its wrapped
    continuation lines), or, for a line without one (bank fees, a transfer to a savings
    account), the free-text lines -- never the IBAN/Kenmerk/Valutadatum bookkeeping around it."""
    fields: dict[str, list[str]] = {}
    free: list[str] = []
    current: str | None = None
    for raw in lines:
        line = _text(raw)
        if not line:
            continue
        match = _KEY_LINE.match(line)
        if match:
            current = match.group(1)
            fields.setdefault(current, []).append(match.group(2))
        elif current is not None:
            fields[current].append(line)
        else:
            free.append(line)
    if fields.get("Omschrijving"):
        # A collector repeats its own name as a wrapped line ("... WWW.SVB.NL", "Sociale
        # Verzekeringsbank") -- already shown as the counterparty, so it's dropped here.
        parts = [p for p in fields["Omschrijving"] if p and p.casefold() != counterparty_name.casefold()]
        return " ".join(parts)
    return " · ".join(free)


def _parse_transaction(raw: dict, account_iban: str) -> BankTransaction | None:
    """One Enable Banking transaction, or None when it isn't a booked, well-formed one (a pending
    entry can still change or vanish, so only booked ones ever reach the ledger)."""
    if raw.get("status") != "BOOK":
        return None
    money = raw.get("transaction_amount") or {}
    amount = _amount(money.get("amount"))
    booked_on = _date(raw.get("booking_date"))
    indicator = raw.get("credit_debit_indicator")
    if amount is None or booked_on is None or indicator not in ("DBIT", "CRDT"):
        return None
    is_debit = indicator == "DBIT"
    party = (raw.get("creditor") if is_debit else raw.get("debtor")) or {}
    party_account = raw.get("creditor_account") if is_debit else raw.get("debtor_account")
    counterparty_name = _text(party.get("name") if isinstance(party, dict) else None, 140)
    lines = [line for line in (raw.get("remittance_information") or []) if isinstance(line, str)]
    # Empty when the bank sends none (Trade Republic); get_transactions fills it in.
    reference = _text(raw.get("entry_reference"), 64)
    code = raw.get("bank_transaction_code") or {}
    return BankTransaction(
        reference=reference,
        amount=amount,
        currency=_text(money.get("currency"), 3) or "EUR",
        is_debit=is_debit,
        booked_on=booked_on,
        transacted_on=_date(raw.get("transaction_date")) or booked_on,
        counterparty_name=counterparty_name,
        counterparty_iban=_iban(party_account),
        description=describe(lines, counterparty_name)[:NOTES_LIMIT],
        method=_text(code.get("description") if isinstance(code, dict) else None, 60),
        raw_text=" ".join(_text(line) for line in lines)[:2000],
    )


def _fill_missing_references(transactions: list[BankTransaction], account_iban: str) -> None:
    """Gives every entry the bank sent without a reference (Trade Republic sends none at all) one
    derived from what identifies it -- account, date, direction, amount, text -- plus its place
    among entries that are otherwise identical, so two €3.95 coffees on one day stay two entries
    and a re-fetch finds the same references again. Relies on the bank listing entries in a stable
    order, which is also what its own pagination relies on."""
    seen: dict[tuple, int] = {}
    for txn in transactions:
        if txn.reference:
            continue
        key = (account_iban, txn.booked_on.isoformat(), txn.is_debit, str(txn.amount), txn.raw_text)
        ordinal = seen.get(key, 0)
        seen[key] = ordinal + 1
        digest = hashlib.sha256("|".join(map(str, (*key, ordinal))).encode()).hexdigest()
        txn.reference = f"h{digest[:40]}"


def _parse_session(data: dict) -> BankSession:
    session_id = _text(data.get("session_id"), 64)
    access = data.get("access") or {}
    try:
        valid_until = datetime.fromisoformat(str(access.get("valid_until")).replace("Z", "+00:00"))
    except ValueError:
        raise EnableBankingError("session without a valid_until")
    if not session_id:
        raise EnableBankingError("session without an id")
    accounts = []
    for raw in data.get("accounts") or []:
        if not isinstance(raw, dict):
            continue
        iban = _iban(raw.get("account_id"))
        uid = _text(raw.get("uid"), 64)
        if not iban or not uid:
            continue
        accounts.append(
            BankAccount(
                uid=uid,
                iban=iban,
                product=_text(raw.get("product"), 60),
                holder_name=_text(raw.get("name"), 120),
                currency=_text(raw.get("currency"), 3) or "EUR",
            )
        )
    return BankSession(session_id=session_id, valid_until=valid_until.astimezone(timezone.utc).replace(tzinfo=None), accounts=accounts)


class EnableBankingProvider:
    def __init__(
        self,
        app_id: str | None = None,
        key_path: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = TIMEOUT,
    ):
        self.app_id = app_id
        self.key_path = key_path
        self.base_url = base_url
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.key_path)

    def _token(self) -> str:
        if not self.configured:
            raise EnableBankingError("Enable Banking is not configured")
        try:
            key = Path(self.key_path).read_text()
        except OSError as exc:
            raise EnableBankingError(f"private key unreadable ({type(exc).__name__})")
        now = int(time.time())
        return jwt.encode(
            {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": now, "exp": now + TOKEN_TTL_SECONDS},
            key,
            algorithm="RS256",
            headers={"kid": self.app_id},
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=self.timeout,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise EnableBankingError(f"Enable Banking unreachable ({type(exc).__name__})")
        if response.status_code == 429:
            raise EnableBankingRateLimitError(f"Enable Banking answered 429: {response.text[:200]}")
        if response.status_code >= 400:
            raise EnableBankingError(f"Enable Banking answered {response.status_code}: {response.text[:200]}")
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError:
            raise EnableBankingError("Enable Banking answered with something that isn't JSON")
        if not isinstance(data, dict):
            raise EnableBankingError("unexpected response shape")
        return data

    def maximum_consent_seconds(self, aspsp_name: str, country: str) -> int | None:
        """How far ahead this bank lets a consent run, from Enable Banking's bank list -- ING allows
        180 days, Trade Republic 90, and a request for longer is refused outright rather than
        shortened. None when the bank isn't listed or says nothing."""
        data = self._request("GET", "/aspsps", params={"country": country})
        for aspsp in data.get("aspsps") or []:
            if isinstance(aspsp, dict) and aspsp.get("name") == aspsp_name:
                value = aspsp.get("maximum_consent_validity")
                return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None
        return None

    def start_authorization(
        self, *, aspsp_name: str, country: str, redirect_url: str, state: str, valid_until: datetime
    ) -> str:
        """Starts a consent and returns the URL to send the reader to (Enable Banking's page,
        which hands over to ING's own login)."""
        data = self._request(
            "POST",
            "/auth",
            json={
                "access": {"valid_until": valid_until.astimezone(timezone.utc).isoformat(timespec="seconds")},
                "aspsp": {"name": aspsp_name, "country": country},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": "personal",
            },
        )
        url = data.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise EnableBankingError("no authorization URL in the response")
        return url

    def create_session(self, code: str) -> BankSession:
        """Turns the one-time code ING's redirect carried into a session."""
        return _parse_session(self._request("POST", "/sessions", json={"code": code}))

    def session_status(self, session_id: str) -> str:
        return _text(self._request("GET", f"/sessions/{session_id}").get("status"), 40)

    def delete_session(self, session_id: str) -> None:
        self._request("DELETE", f"/sessions/{session_id}")

    def get_transactions(self, session_id: str, account_uid: str, iban: str, date_from: date) -> list[BankTransaction]:
        """Every booked transaction on the account since `date_from`, all pages. A failure on a
        session that's no longer authorized is reported as EnableBankingSessionError, so the
        caller can ask for a reconnect instead of retrying tomorrow.

        Some banks (Trade Republic) ignore `date_from` and page through the whole history, newest
        first -- and every page counts toward the few reads a day PSD2 lets a bank allow without
        the reader present. So entries before `date_from` are dropped here, and the first page
        that reaches back past `date_from` ends the paging: everything after it is older still."""
        transactions: list[BankTransaction] = []
        continuation: str | None = None
        for _ in range(MAX_PAGES):
            params = {"date_from": date_from.isoformat()}
            if continuation:
                params["continuation_key"] = continuation
            try:
                data = self._request("GET", f"/accounts/{account_uid}/transactions", params=params)
            except EnableBankingRateLimitError:
                raise  # the consent is fine; asking about it now would only be another request
            except EnableBankingError:
                self._raise_if_session_gone(session_id)
                raise
            page = [p for p in (_parse_transaction(raw, iban) for raw in data.get("transactions") or [] if isinstance(raw, dict)) if p]
            transactions.extend(t for t in page if t.booked_on >= date_from)
            continuation = data.get("continuation_key") or None
            if not continuation or any(t.booked_on < date_from for t in page):
                break
        _fill_missing_references(transactions, iban)
        return transactions

    def _raise_if_session_gone(self, session_id: str) -> None:
        try:
            status = self.session_status(session_id)
        except EnableBankingError:
            return  # can't tell -- let the original error stand
        if status != "AUTHORIZED":
            raise EnableBankingSessionError(f"session is {status or 'unknown'}")


enablebanking_provider = EnableBankingProvider(config.ENABLEBANKING_APP_ID, config.ENABLEBANKING_KEY_PATH)
