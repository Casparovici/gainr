"""One-off import of a Transaction-shaped sheet from an xlsx workbook into the database.

Usage (from backend/):
    python -m scripts.import_transactions ../portfolio.xlsx
    python -m scripts.import_transactions ../portfolio_kids.xlsx --portfolio Kids --sheet "Kids Transaction"

Imports into the "Main" portfolio by default (get-or-create by name); --portfolio names a
different one, created if it doesn't exist yet — see docs/adr/0019. Reads the worksheet named
"Transaction" by default; --sheet names a different one, for a workbook whose sheet is named
after its own portfolio rather than the generic "Transaction" the original portfolio.xlsx uses.

Idempotent: re-running matches existing rows by their source row number before inserting,
so it's safe to run again (e.g. after fixing a mapping) without duplicating rows. Rows imported
into Main keep the original, unprefixed source_ref format (`xlsx:Transaction:row{n}`) for zero
risk to already-imported rows' idempotency; any other portfolio's rows are prefixed with the
portfolio name (`xlsx:{portfolio}:Transaction:row{n}`) since those are fresh imports with no
legacy format to preserve.
"""

import argparse
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models.transaction import CASH_ONLY_TYPES, TransactionType  # noqa: E402
from app.repositories import asset_repo, portfolio_repo, transaction_repo  # noqa: E402
from app.services.portfolio_service import MAIN_PORTFOLIO_NAME  # noqa: E402
from app.services.price_service import price_service  # noqa: E402

HEADER_ROW = 1
COLUMNS = ["date", "type", "ticker", "stock", "amount", "price", "local_value", "fx", "value", "costs", "total", "broker"]

# Heuristic ticker -> yahoo_symbol mapping. Exchange-prefixed tickers (e.g. "AMS:TDIV") and
# crypto pairs (e.g. "ETHEUR") need translating; anything not covered here is imported with
# no yahoo_symbol and shows as "price unavailable" until corrected via the asset editor.
EXCHANGE_SUFFIX = {
    "NASDAQ": "",
    "NYSE": "",
    "AMS": ".AS",
    "EPA": ".PA",
    "ETR": ".DE",
    "LON": ".L",
    "BIT": ".MI",
}
MANUAL_OVERRIDES = {
    "4GLD": "4GLD.DE",
    "CASH": None,
    # Verified by symbol name/price match against the ledger (source sheet had no
    # exchange prefix for these three, so the generic heuristic can't place them).
    "GRIDINAV": "GRID.MI",  # Borsa Italiana listing, not Amsterdam
    "SMH": "SMH.MI",  # Borsa Italiana listing (confirmed with user), not the US NASDAQ:SMH
    "ABN": "ABN.AS",
    "TNIE": "TNIE.DE",
    "ADYEN": "ADYEN.AS",
    "BATS": "BATS.L",
    "LIGHT": "LIGHT.AS",
    "SEMB": "SEMB.L",
    "SSHY": "SSHY.L",
    "STHS": "STHS.L",
    "VGOV": "VGOV.L",
    "VUSC": "VUSC.L",
    "IMAE": "IMAE.AS",
    "NYSE:SQ": "XYZ",  # Block Inc renamed its ticker from SQ to XYZ
}

# Rows where the sheet's Date cell is empty (3 "smh" buys with no date entered). Confirmed
# with the user (2026-09-09) that all three happened on 2026-06-30.
MISSING_DATE_OVERRIDES: dict[int, date] = {
    1158: date(2026, 6, 30),
    1159: date(2026, 6, 30),
    1160: date(2026, 6, 30),
}


def normalize_ticker(ticker: str) -> str:
    """The source sheet has inconsistent casing for a handful of tickers (e.g. "baba" /
    "BABA" for the same stock) which would otherwise import as two separate assets."""
    if ":" in ticker:
        exchange, symbol = ticker.split(":", 1)
        return f"{exchange.upper()}:{symbol.upper()}"
    return ticker.upper()


def is_crypto_eur_pair(ticker: str) -> bool:
    return ":" not in ticker and ticker.endswith("EUR") and len(ticker) > 3


def guess_yahoo_symbol(ticker: str) -> str | None:
    if ticker in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[ticker]
    if is_crypto_eur_pair(ticker):
        return f"{ticker[:-3]}-EUR"
    if ":" in ticker:
        exchange, symbol = ticker.split(":", 1)
        suffix = EXCHANGE_SUFFIX.get(exchange.upper())
        if suffix is not None:
            return f"{symbol}{suffix}"
        return None
    return ticker


def guess_asset_class(ticker: str) -> str:
    if is_crypto_eur_pair(ticker):
        return "crypto"
    if ticker == "4GLD":
        return "commodity"
    if ticker == "CASH":
        return "cash"
    return "equity"


def to_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def main(xlsx_path: str, portfolio_name: str = MAIN_PORTFOLIO_NAME, sheet_name: str = "Transaction") -> None:
    Base.metadata.create_all(bind=engine)
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[sheet_name]

    db = SessionLocal()
    inserted = 0
    skipped_existing = 0
    unmapped: set[str] = set()

    try:
        portfolio = portfolio_repo.get_by_name(db, portfolio_name)
        if portfolio is None:
            portfolio = portfolio_repo.create_portfolio(db, portfolio_name)
            db.commit()
        source_ref_prefix = "xlsx:Transaction:row" if portfolio_name == MAIN_PORTFOLIO_NAME else f"xlsx:{portfolio_name}:Transaction:row"

        for row_idx in range(HEADER_ROW + 1, ws.max_row + 1):
            row = [ws.cell(row=row_idx, column=c).value for c in range(1, len(COLUMNS) + 1)]
            if row[0] is None and row_idx not in MISSING_DATE_OVERRIDES:
                continue
            record = dict(zip(COLUMNS, row))

            txn_date = record["date"].date() if record["date"] is not None else MISSING_DATE_OVERRIDES[row_idx]
            txn_type = TransactionType(record["type"])
            ticker = normalize_ticker(record["ticker"]) if record["ticker"] else None

            asset_id = None
            if ticker and txn_type not in CASH_ONLY_TYPES:
                asset = asset_repo.get_by_ticker(db, ticker)
                if asset is None:
                    yahoo_symbol = guess_yahoo_symbol(ticker)
                    if yahoo_symbol is None:
                        unmapped.add(ticker)
                    asset = asset_repo.create_asset(
                        db,
                        ticker=ticker,
                        name=record["stock"] or ticker,
                        asset_class=guess_asset_class(ticker),
                        native_currency="EUR",
                        yahoo_symbol=yahoo_symbol,
                    )
                asset_id = asset.id

            total_eur = to_decimal(record["total"]) or Decimal(0)
            source_ref = f"{source_ref_prefix}{row_idx}"

            if transaction_repo.exists_by_source_ref(db, source_ref):
                skipped_existing += 1
                continue

            transaction_repo.create_transaction(
                db,
                portfolio_id=portfolio.id,
                asset_id=asset_id,
                date=txn_date,
                type=txn_type,
                quantity=to_decimal(record["amount"]),
                price=to_decimal(record["price"]),
                local_value=to_decimal(record["local_value"]),
                fx_rate=to_decimal(record["fx"]),
                value_eur=to_decimal(record["value"]) or Decimal(0),
                costs=to_decimal(record["costs"]) or Decimal(0),
                total_eur=total_eur,
                broker=record["broker"],
                source_ref=source_ref,
            )
            inserted += 1

        db.commit()

        print("Syncing native currency/price scale from the price provider (one call per asset)...")
        synced = 0
        for asset in asset_repo.list_assets(db):
            if asset.asset_class == "fx" or not asset.yahoo_symbol:
                continue
            before = (asset.native_currency, asset.price_scale)
            price_service.sync_currency(db, asset)
            if (asset.native_currency, asset.price_scale) != before:
                synced += 1
        db.commit()
        print(f"Currency sync changed {synced} assets.")
    finally:
        db.close()

    print(f"Inserted {inserted} transactions, skipped {skipped_existing} already-imported rows.")
    if unmapped:
        print(f"{len(unmapped)} tickers have no price-provider symbol guess (edit via the asset editor): {sorted(unmapped)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx_path")
    parser.add_argument("--portfolio", default=MAIN_PORTFOLIO_NAME, help='Portfolio to import into (default: "Main")')
    parser.add_argument("--sheet", default="Transaction", help='Worksheet to read (default: "Transaction")')
    args = parser.parse_args()
    main(args.xlsx_path, args.portfolio, args.sheet)
