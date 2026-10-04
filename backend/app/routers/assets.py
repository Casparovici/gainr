import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import asset_repo, position_note_label_repo, position_note_repo
from app.schemas.asset import AssetCreate, AssetOut, AssetTargetWeightIn, AssetUpdate, SymbolLookupOut, SymbolMatchOut
from app.schemas.position_note import PositionNoteCreate, PositionNoteOut, PositionNoteUpdate
from app.services.logo_service import logo_service
from app.services.price_service import price_service
from app.services.target_weight_service import TargetWeightExceeded, set_asset_target_weight

router = APIRouter(prefix="/api/assets", tags=["assets"])


# Synthetic pseudo-assets (FX pairs, benchmark indices) share the assets table to reuse the
# price cache, but they aren't holdings and shouldn't show up as selectable assets.
SYNTHETIC_CLASSES = {"fx", "benchmark"}

# "no-cache" means "keep it, but check with me before using it" — not "don't store it". The
# browser keeps its copy and we answer 304 with no body while the bytes are unchanged, so a
# Home render costs a handful of conditional requests to localhost. An expiry instead of a
# validator is what let an improved logo sit invisible behind a day-old copy: the browser had
# no reason to ask.
LOGO_CACHE_CONTROL = "no-cache"


@router.get("", response_model=list[AssetOut])
def list_assets(db: Session = Depends(get_db)):
    return [a for a in asset_repo.list_assets(db) if a.asset_class not in SYNTHETIC_CLASSES]


@router.get("/lookup", response_model=SymbolLookupOut)
def lookup_symbol(q: str = Query(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9 .:^=&-]+$")):
    """The listings the price provider knows for a ticker, ISIN or name -- shown while adding an
    asset, so its price symbol is picked from what actually exists (IQQW.DE rather than a bare
    "IQQW" Yahoo has never heard of) and the reader sees *which* fund a symbol is."""
    query = q.strip()
    matches = price_service.provider.search(query)
    # The query itself first when it's a listing, the provider's own ranking after that.
    matches.sort(key=lambda m: m.symbol.upper() != query.upper())
    return SymbolLookupOut(
        query=query,
        exact=any(m.symbol.upper() == query.upper() for m in matches),
        matches=[SymbolMatchOut(symbol=m.symbol, name=m.name, exchange=m.exchange, quote_type=m.quote_type) for m in matches],
    )


@router.post("", response_model=AssetOut)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)):
    """Get-or-create by ticker — `assets.ticker` is already unique, so re-submitting a ticker
    that exists returns that asset rather than erroring, matching what a caller adding a
    transaction actually wants (an id to buy against, new or not). A new asset takes its currency
    from the price provider when it can (and catches London quotes in pence), rather than trusting
    a field the reader may have left at its EUR default."""
    existing = asset_repo.get_by_ticker(db, payload.ticker)
    asset = asset_repo.get_or_create_asset(
        db,
        ticker=payload.ticker,
        name=payload.name,
        asset_class=payload.asset_class,
        native_currency=payload.native_currency,
        yahoo_symbol=payload.yahoo_symbol or payload.ticker,
    )
    if existing is None:
        price_service.sync_currency(db, asset)
    if payload.isin and not asset.isin:
        asset.isin = payload.isin
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{asset_id}/logo")
def get_asset_logo(asset_id: int, request: Request, db: Session = Depends(get_db)):
    """The asset's brand icon as raw image bytes, or 404 when there isn't one.

    Served from our own origin rather than as a redirect to the issuer's site: the cached
    copy keeps working when the issuer moves the file, and the browser never gets told which
    companies this portfolio holds.
    """
    asset = asset_repo.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    logo = logo_service.get_logo(db, asset)
    if logo is None:
        # Plain Response, not HTTPException — the callers are <img> tags that fall back to an
        # initials badge, so there's nothing to explain in a body. Re-asking is cheap: the
        # per-day gate means a miss is answered from the database without touching the network.
        return Response(status_code=404, headers={"Cache-Control": LOGO_CACHE_CONTROL})

    # Content-addressed, so the tag changes exactly when the image does — including when the
    # same asset re-resolves to a better source.
    etag = f'"{hashlib.sha1(logo.image).hexdigest()}"'
    headers = {"Cache-Control": LOGO_CACHE_CONTROL, "ETag": etag}

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return Response(content=logo.image, media_type=logo.content_type, headers=headers)


@router.put("/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: int, payload: AssetUpdate, db: Session = Depends(get_db)):
    asset = asset_repo.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    fields = payload.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset


@router.put("/{asset_id}/target-weight", response_model=AssetTargetWeightIn)
def update_asset_target_weight(asset_id: int, payload: AssetTargetWeightIn, db: Session = Depends(get_db)):
    if asset_repo.get_asset(db, asset_id) is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        set_asset_target_weight(db, payload.portfolio_id, asset_id, payload.target_weight_pct)
    except TargetWeightExceeded as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return payload


# -- position notes -----------------------------------------------------------------------------


@router.get("/{asset_id}/notes", response_model=list[PositionNoteOut])
def list_position_notes(asset_id: int, db: Session = Depends(get_db)):
    if asset_repo.get_asset(db, asset_id) is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return position_note_repo.list_notes(db, asset_id)


@router.post("/{asset_id}/notes", response_model=PositionNoteOut)
def create_position_note(asset_id: int, payload: PositionNoteCreate, db: Session = Depends(get_db)):
    if asset_repo.get_asset(db, asset_id) is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    fields = payload.model_dump(exclude={"label_ids"})
    labels = position_note_label_repo.get_by_ids(db, payload.label_ids)
    note = position_note_repo.create_note(db, assets=[asset_repo.get_asset(db, asset_id)], labels=labels, **fields)
    db.commit()
    db.refresh(note)
    return note


@router.put("/{asset_id}/notes/{note_id}", response_model=PositionNoteOut)
def update_position_note(asset_id: int, note_id: int, payload: PositionNoteUpdate, db: Session = Depends(get_db)):
    note = position_note_repo.get_note(db, note_id)
    if note is None or not position_note_repo.is_linked(note, asset_id):
        raise HTTPException(status_code=404, detail="Note not found")
    fields = payload.model_dump(exclude_unset=True, exclude={"label_ids"})
    if payload.label_ids is not None:
        fields["labels"] = position_note_label_repo.get_by_ids(db, payload.label_ids)
    position_note_repo.update_note(db, note, **fields)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{asset_id}/notes/{note_id}", status_code=204)
def delete_position_note(asset_id: int, note_id: int, db: Session = Depends(get_db)):
    note = position_note_repo.get_note(db, note_id)
    if note is None or not position_note_repo.is_linked(note, asset_id):
        raise HTTPException(status_code=404, detail="Note not found")
    # Deletes the note itself, wherever else it's linked -- the Notes tab's confirmation says so.
    position_note_repo.delete_note(db, note)
    db.commit()
