"""Re-keys the counterparties already recorded by the bank sync to the current matching key (see
bank_sync_service.normalize_merchant), so categories learned before the key changed keep
matching. A bank-booked row still carries the bank's counterparty in its notes ("Albert Heijn
1234 Amsterdam — ..."), which is re-keyed from; any other row keeps what it has. Safe to run
again: a row already on the current key is left as it is.

Usage (from backend/):
    python -m scripts.rekey_merchants
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.bank_sync import BankSyncedTransaction  # noqa: E402
from app.models.gripr_transaction import GriprTransaction  # noqa: E402
from app.services.bank_sync_service import normalize_merchant  # noqa: E402


def rekey(db) -> int:
    rows = db.execute(
        select(BankSyncedTransaction, GriprTransaction.notes)
        .join(GriprTransaction, GriprTransaction.id == BankSyncedTransaction.gripr_transaction_id)
        .where(BankSyncedTransaction.merchant.is_not(None), BankSyncedTransaction.outcome == "booked")
    ).all()
    changed = 0
    for synced, notes in rows:
        counterparty = (notes or "").split(" — ")[0].strip()
        key = normalize_merchant(counterparty) if counterparty else None
        if key and key != synced.merchant:
            synced.merchant = key
            changed += 1
    db.flush()
    return changed


def main() -> None:
    with SessionLocal() as db:
        changed = rekey(db)
        db.commit()
    print(f"Re-keyed {changed} counterparty record(s).")


if __name__ == "__main__":
    main()
