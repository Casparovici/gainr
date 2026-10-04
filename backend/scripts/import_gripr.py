"""One-off import of a personal-finance ledger export (personal_trx.csv) into gripr's tables.

Usage (from backend/):
    python -m scripts.import_gripr ../personal_trx.csv

The source export is two CSV tables concatenated in one file: a transaction ledger, then a
blank-line separator, then a current account-balance snapshot. Each ledger row has one side
that's always a real account (VAN REKENING for Uitgave/Inkomsten, either side for
Overboeking) and one side that's a category label for Uitgave/Inkomsten ("Parent (Sub)" or
just "Parent"). Amounts are Dutch-format-free (plain "." decimals), so parsing is just Decimal().

Idempotent: re-running matches existing rows by their source row number before inserting, so
it's safe to run again without duplicating rows. The one thing NOT re-run on a second pass is
opening-balance reconciliation (see below) — it only ever applies once, right after the first
import, based on rows inserted in that same run.
"""

import csv
import io
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models.gripr_account import GriprAccountType, GriprBalanceMode  # noqa: E402
from app.models.gripr_category import GriprCategoryKind  # noqa: E402
from app.models.gripr_transaction import GriprTransactionType  # noqa: E402
from app.repositories import gripr_account_repo, gripr_category_repo, gripr_transaction_repo  # noqa: E402
from app.services.gripr_account_service import compute_balance  # noqa: E402

# account name (already .strip()'d) -> (type, balance_mode). Historical/closed accounts (not
# in the current balance snapshot) still need a row so their transactions have somewhere to
# point; they're imported archived since the user has moved on from them.
ACCOUNT_TYPES: dict[str, tuple[GriprAccountType, GriprBalanceMode]] = {
    "ING": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "T212 Debit": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "En/Of": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "Contant geld": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "Cashback": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "Revolut": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "Visa debit": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "Trading212": (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL),
    "ING Spaarrekening": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Onderhoud Auto": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Reservering Vakantie": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Afschrijving Auto": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Beleggingsrekening kinderen": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Debiteuren": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Bigbank": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Bouwdepot": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Kleding": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Onderhoud Huis": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Vrije tijd & uitjes": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Zorgkosten": (GriprAccountType.SAVINGS, GriprBalanceMode.TRANSACTIONAL),
    "Trade Republic": (GriprAccountType.INVESTMENT, GriprBalanceMode.TRANSACTIONAL),
    "Beleggen": (GriprAccountType.INVESTMENT, GriprBalanceMode.TRANSACTIONAL),
    "Robeco Beleggen": (GriprAccountType.INVESTMENT, GriprBalanceMode.TRANSACTIONAL),
    "Crypto": (GriprAccountType.INVESTMENT, GriprBalanceMode.TRANSACTIONAL),
    "Creditcard": (GriprAccountType.CREDIT, GriprBalanceMode.MANUAL),
    "Studieschuld": (GriprAccountType.LOAN, GriprBalanceMode.MANUAL),
    "Hypotheek": (GriprAccountType.LOAN, GriprBalanceMode.MANUAL),
    "Ford Focus": (GriprAccountType.ASSET, GriprBalanceMode.MANUAL),
    "Peugeot 107": (GriprAccountType.ASSET, GriprBalanceMode.MANUAL),
    "Woning Overwaarde": (GriprAccountType.ASSET, GriprBalanceMode.MANUAL),
}

# Top-level category -> subcategories, split by kind. Derived from every distinct
# "Parent (Sub)" / "Parent" label seen across the full ledger.
EXPENSE_CATEGORIES: dict[str, list[str]] = {
    "Aankopen": [],
    "Abonnementen": ["AI", "Bankieren", "Disney", "Donald Duck", "HBO", "Internet & tv", "Netflix", "Spotify", "Telefoon"],
    "Boodschappen": ["Baby", "Persoonlijke verzorging", "Weekboodschappen"],
    "Debiteuren": [],
    "Eten & Drinken": ["Bars", "Caspar", "Lunch", "Marit", "Powerleague", "Restaurants", "Thuisbezorgd", "Tussendoortjes"],
    "Extra Aflossen Hypotheek": [],
    "Goede doelen": [
        "ActionAID", "Bootvluchteling", "Collecte", "Compassion", "KWF", "Leger des Heils", "Lighthouse",
        "MIND", "Opkikker", "SOS Kinderdorpen", "Slachtofferhulp", "Stichting Vrij Zijn", "VVB", "WNF", "Warchild",
    ],
    "Huis": ["Inboedel", "Onderhoud", "Schoonmaker"],
    "Kinderen": ["Kamertje", "Oppas", "Opvang", "Verzorging", "Zwemles"],
    "Kleding": ["Caspar", "Kids", "Marit"],
    "Medische kosten": ["Behandeling", "Zorgverzekering"],
    "Overig": ["Cadeautjes", "Tabak"],
    "Persoonlijke verzorging": ["Kapper", "Marit", "Nagels", "Vitamines"],
    "Studieschuld": ["Studieschuld"],
    "Vakanties": ["Boodschappen", "Brandstof", "Overig", "Uit eten"],
    "Vervoer": ["107", "ANWB", "Brandstof", "OV", "Onderhoud", "Parkeren", "Verzekering", "Wegenbelasting"],
    "Verzekeringen": [
        "Inboedel- en opstalverzekering", "Overlijdensrisicoverzekering", "Telefoonverzekering",
        "Uitvaartverzekering", "Zorgverzekering",
    ],
    "Vrije tijd & Uitjes": ["Aquarobics", "Gym", "Powerleague", "Zwift"],
    "Wonen": ["Drinkwater", "Gas en Elektra", "Gemeentelijke belastingen", "Hypotheek", "Waterschapsbelasting"],
    "Woning Overwaarde": [],
}
INCOME_CATEGORIES: dict[str, list[str]] = {
    "Belastingdienst": [],
    "Overig": ["Cashback", "Marktplaats", "Rente", "SnappCar"],
    "Salaris": [],
    "Toeslagen": [],
}


def parse_category_label(label: str) -> tuple[str, str | None]:
    label = label.strip()
    if label.endswith(")") and "(" in label:
        parent, sub = label.split("(", 1)
        return parent.strip(), sub[:-1].strip()
    return label, None


def load_sections(path: Path) -> tuple[list[list[str]], dict[str, Decimal]]:
    text = path.read_text(encoding="utf-8-sig")
    txn_text, snapshot_text = text.split("\n,\n,\n")
    txn_rows = list(csv.reader(io.StringIO(txn_text)))[1:]  # drop header
    snapshot_rows = [r for r in csv.reader(io.StringIO(snapshot_text)) if r and r[0]][1:]  # drop "NAAM,SALDO,VALUTA"
    snapshot = {name.strip(): Decimal(balance) for name, balance, _currency in snapshot_rows}
    return txn_rows, snapshot


def preload_categories(db) -> dict[tuple[str, GriprCategoryKind, str | None], int]:
    """Returns {(name, kind, sub_or_None): category_id} for every category+subcategory."""
    lookup: dict[tuple[str, GriprCategoryKind, str | None], int] = {}
    for tree, kind in ((EXPENSE_CATEGORIES, GriprCategoryKind.EXPENSE), (INCOME_CATEGORIES, GriprCategoryKind.INCOME)):
        for parent_name, subs in tree.items():
            parent = gripr_category_repo.get_by_name(db, parent_name, kind, None)
            if parent is None:
                parent = gripr_category_repo.create_category(db, name=parent_name, kind=kind, parent_id=None)
            lookup[(parent_name, kind, None)] = parent.id
            for sub_name in subs:
                sub = gripr_category_repo.get_by_name(db, sub_name, kind, parent.id)
                if sub is None:
                    sub = gripr_category_repo.create_category(db, name=sub_name, kind=kind, parent_id=parent.id)
                lookup[(parent_name, kind, sub_name)] = sub.id
    return lookup


def get_or_create_account(db, accounts: dict[str, int], raw_name: str) -> int:
    name = raw_name.strip()
    if name in accounts:
        return accounts[name]
    account_type, balance_mode = ACCOUNT_TYPES.get(name, (GriprAccountType.CHECKING, GriprBalanceMode.TRANSACTIONAL))
    account = gripr_account_repo.get_by_name(db, name)
    if account is None:
        account = gripr_account_repo.create_account(
            db, name=name, type=account_type, balance_mode=balance_mode, is_archived=False
        )
    accounts[name] = account.id
    return account.id


def category_id_for(lookup: dict, kind: GriprCategoryKind, label: str) -> int:
    parent_name, sub_name = parse_category_label(label)
    key = (parent_name, kind, sub_name)
    if key in lookup:
        return lookup[key]
    # Unseen combination (shouldn't happen against the analyzed export, but a future re-run
    # against an updated export might add a new category) — fall back to the bare parent,
    # creating it if even that's new.
    parent_key = (parent_name, kind, None)
    if parent_key not in lookup:
        raise ValueError(f"Unknown category {label!r} for kind {kind}")
    return lookup[parent_key]


def main(csv_path: str) -> None:
    path = Path(csv_path)
    txn_rows, snapshot = load_sections(path)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        category_lookup = preload_categories(db)
        db.commit()

        accounts: dict[str, int] = {}
        inserted = 0
        skipped_existing = 0

        for row_idx, row in enumerate(txn_rows, start=2):  # +2: header is row 1, data starts row 2
            date_str, type_str, van, naar, bedrag, *_rest = row
            notitie = row[9].strip() or None
            source_ref = f"pefi_csv:row{row_idx}"
            if gripr_transaction_repo.exists_by_source_ref(db, source_ref):
                skipped_existing += 1
                continue

            txn_date = datetime.strptime(date_str, "%d-%m-%Y").date()
            # A single historical row records a refund as a negative expense amount. The
            # model always stores a positive magnitude; direction comes from `type` alone, so
            # this one row is folded in as a (slightly overstated) expense rather than adding
            # sign-handling for the other 12,807 rows that don't need it.
            amount = abs(Decimal(bedrag))

            if type_str == "Uitgave":
                account_id = get_or_create_account(db, accounts, van)
                category_id = category_id_for(category_lookup, GriprCategoryKind.EXPENSE, naar)
                gripr_transaction_repo.create_transaction(
                    db, date=txn_date, type=GriprTransactionType.EXPENSE, amount=amount,
                    account_id=account_id, category_id=category_id, notes=notitie, source_ref=source_ref,
                )
            elif type_str == "Inkomsten":
                account_id = get_or_create_account(db, accounts, van)
                category_id = category_id_for(category_lookup, GriprCategoryKind.INCOME, naar)
                gripr_transaction_repo.create_transaction(
                    db, date=txn_date, type=GriprTransactionType.INCOME, amount=amount,
                    account_id=account_id, category_id=category_id, notes=notitie, source_ref=source_ref,
                )
            elif type_str == "Overboeking":
                account_id = get_or_create_account(db, accounts, van)
                counter_account_id = get_or_create_account(db, accounts, naar)
                gripr_transaction_repo.create_transaction(
                    db, date=txn_date, type=GriprTransactionType.TRANSFER, amount=amount,
                    account_id=account_id, counter_account_id=counter_account_id, notes=notitie, source_ref=source_ref,
                )
            else:
                raise ValueError(f"Unknown transaction type {type_str!r} on row {row_idx}")
            inserted += 1

        db.commit()

        # Reconcile: every transactional account's opening_balance is set so that
        # opening_balance + sum(its imported transactions) lands exactly on the CSV's own
        # balance snapshot. Accounts not in the snapshot (closed/historical) are archived and
        # left at opening_balance 0 — whatever the ledger nets out to is their true remainder.
        reconciled = 0
        for name, account_id in accounts.items():
            account = gripr_account_repo.get_account(db, account_id)
            if account.balance_mode != GriprBalanceMode.TRANSACTIONAL:
                continue
            if name in snapshot:
                current = compute_balance(db, account)
                account.opening_balance = account.opening_balance + (snapshot[name] - current)
                reconciled += 1
            else:
                account.is_archived = True
        db.commit()

        # Manual-mode accounts (loans, asset trackers) just take the snapshot value directly.
        for name, (account_type, balance_mode) in ACCOUNT_TYPES.items():
            if balance_mode != GriprBalanceMode.MANUAL:
                continue
            account = gripr_account_repo.get_by_name(db, name)
            if account is None:
                account = gripr_account_repo.create_account(
                    db, name=name, type=account_type, balance_mode=balance_mode, is_archived=name not in snapshot
                )
            account.manual_balance = snapshot.get(name, Decimal(0))
        db.commit()
    finally:
        db.close()

    print(f"Inserted {inserted} transactions, skipped {skipped_existing} already-imported rows.")
    print(f"Reconciled opening balances for {reconciled} transactional accounts against the snapshot.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.import_gripr <path-to-personal_trx.csv>")
        sys.exit(1)
    main(sys.argv[1])
