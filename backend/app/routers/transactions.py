import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import transaction_attachment_repo, transaction_repo
from app.schemas.transaction import (
    TransactionAttachmentOut,
    TransactionCreate,
    TransactionOut,
    TransactionPage,
    TransactionUpdate,
)
from app.services import transaction_attachment_service
from app.services.performance_service import performance_service

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

CSV_COLUMNS = [
    "date", "type", "ticker", "asset_name", "quantity", "price", "native_currency",
    "local_value", "fx_rate", "value_eur", "costs", "total_eur", "broker", "to_broker", "notes",
]


def _to_out(txn, attachment_count: int = 0) -> TransactionOut:
    return TransactionOut(
        id=txn.id,
        date=txn.date,
        type=txn.type,
        portfolio_id=txn.portfolio_id,
        asset_id=txn.asset_id,
        quantity=txn.quantity,
        price=txn.price,
        local_value=txn.local_value,
        fx_rate=txn.fx_rate,
        value_eur=txn.value_eur,
        costs=txn.costs,
        total_eur=txn.total_eur,
        broker=txn.broker,
        to_broker=txn.to_broker,
        notes=txn.notes,
        ticker=txn.asset.ticker if txn.asset else None,
        asset_name=txn.asset.name if txn.asset else None,
        native_currency=txn.asset.native_currency if txn.asset else None,
        attachment_count=attachment_count,
    )


@router.get("/export.csv")
def export_transactions_csv(portfolio_id: int, db: Session = Depends(get_db)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for txn in transaction_repo.list_all_transactions(db, portfolio_id):
        writer.writerow(
            [
                txn.date.isoformat(),
                txn.type.value,
                txn.asset.ticker if txn.asset else "",
                txn.asset.name if txn.asset else "",
                txn.quantity,
                txn.price,
                txn.asset.native_currency if txn.asset else "",
                txn.local_value,
                txn.fx_rate,
                txn.value_eur,
                txn.costs,
                txn.total_eur,
                txn.broker,
                txn.to_broker,
                txn.notes,
            ]
        )
    buffer.seek(0)
    filename = f"gainr-transactions-{date.today().isoformat()}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=TransactionPage)
def list_transactions(
    portfolio_id: int,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "date",
    sort_dir: str = "desc",
    asset_name: str | None = None,
    asset_id: int | None = None,
    txn_type: str | None = Query(default=None, alias="type"),
    broker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    cash_movements: bool = False,
    db: Session = Depends(get_db),
):
    items, total = transaction_repo.list_transactions(
        db, portfolio_id, offset=offset, limit=limit, sort_by=sort_by, sort_dir=sort_dir, asset_name=asset_name,
        asset_id=asset_id, type_filter=txn_type, broker=broker, date_from=date_from, date_to=date_to,
        cash_movements=cash_movements,
    )
    counts = transaction_attachment_repo.counts_by_transaction(db, [t.id for t in items])
    return TransactionPage(items=[_to_out(t, counts.get(t.id, 0)) for t in items], total=total)


@router.get("/brokers", response_model=list[str])
def list_brokers(portfolio_id: int, db: Session = Depends(get_db)):
    return transaction_repo.list_distinct_brokers(db, portfolio_id)


@router.post("", response_model=TransactionOut)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    txn = transaction_repo.create_transaction(db, **payload.model_dump())
    db.commit()
    db.refresh(txn)
    performance_service.invalidate_cache(txn.portfolio_id)
    return _to_out(txn)


@router.put("/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    txn = transaction_repo.get_transaction(db, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    old_portfolio_id = txn.portfolio_id
    transaction_repo.update_transaction(db, txn, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(txn)
    performance_service.invalidate_cache(old_portfolio_id)
    if txn.portfolio_id != old_portfolio_id:
        performance_service.invalidate_cache(txn.portfolio_id)
    return _to_out(txn, transaction_attachment_repo.count_for_transaction(db, txn.id))


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    txn = transaction_repo.get_transaction(db, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    portfolio_id = txn.portfolio_id
    transaction_repo.delete_transaction(db, txn)
    db.commit()
    performance_service.invalidate_cache(portfolio_id)


# -- attachments (invoices, contract notes) ---------------------------------------------------


def _get_transaction_or_404(db: Session, transaction_id: int):
    txn = transaction_repo.get_transaction(db, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.get("/{transaction_id}/attachments", response_model=list[TransactionAttachmentOut])
def list_attachments(transaction_id: int, db: Session = Depends(get_db)):
    _get_transaction_or_404(db, transaction_id)
    return transaction_attachment_repo.list_for_transaction(db, transaction_id)


@router.post("/{transaction_id}/attachments", response_model=TransactionAttachmentOut, status_code=201)
def add_attachment(transaction_id: int, file: UploadFile, db: Session = Depends(get_db)):
    """A deliberate attach action, separate from the transaction's own JSON create/update."""
    _get_transaction_or_404(db, transaction_id)
    try:
        accepted, content = transaction_attachment_service.accept_upload(
            file.file, file.filename, transaction_attachment_repo.count_for_transaction(db, transaction_id)
        )
    except transaction_attachment_service.AttachmentRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    attachment = transaction_attachment_repo.create(
        db,
        transaction_id=transaction_id,
        filename=accepted.filename,
        content_type=accepted.content_type,
        size_bytes=accepted.size_bytes,
        content=content,
    )
    db.commit()
    db.refresh(attachment)
    return attachment


def _get_attachment_or_404(db: Session, transaction_id: int, attachment_id: int):
    attachment = transaction_attachment_repo.get_with_content(db, attachment_id)
    # An id from a different transaction is as good as unknown, not something to serve.
    if attachment is None or attachment.transaction_id != transaction_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


@router.get("/{transaction_id}/attachments/{attachment_id}")
def get_attachment(transaction_id: int, attachment_id: int, db: Session = Depends(get_db)):
    attachment = _get_attachment_or_404(db, transaction_id, attachment_id)
    return Response(
        content=attachment.content,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": transaction_attachment_service.content_disposition(attachment.filename),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{transaction_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(transaction_id: int, attachment_id: int, db: Session = Depends(get_db)):
    attachment = _get_attachment_or_404(db, transaction_id, attachment_id)
    transaction_attachment_repo.delete(db, attachment)
    db.commit()
