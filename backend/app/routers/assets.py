import hashlib
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import asset_repo
from app.schemas.asset import (
    AssetCreate,
    AssetOut,
    AssetTargetWeightIn,
    AssetUpdate,
    PriceChartOut,
    PricePointOut,
    SymbolLookupOut,
    SymbolMatchOut,
)
from app.services.logo_service import logo_service
from app.services.price_chart_service import price_chart_service
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


@router.get("/{asset_id}/prices", response_model=PriceChartOut)
def get_price_chart(
    asset_id: int,
    range_key: Literal["1D", "1W", "1M", "YTD", "3Y"] = Query("1M", alias="range"),
    db: Session = Depends(get_db),
):
    """The position's own price over a range, in its trading currency (docs/adr/0053): daily
    closes, with today's live quote, or for 1D the last session through the day. An asset with no
    price symbol (a manual holding, cash) has no prices: an empty chart, not an error."""
    asset = asset_repo.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    chart = price_chart_service.build(db, asset, range_key, date.today())
    db.commit()  # a range that reached back past the cache backfilled it
    return PriceChartOut(
        range=chart.range,
        currency=chart.currency,
        interval=chart.interval,
        points=[PricePointOut(time=p.time, price=p.price) for p in chart.points],
        start_price=chart.start_price,
        end_price=chart.end_price,
        change=chart.change,
        change_pct=chart.change_pct,
        is_fallback=chart.is_fallback,
        as_of=chart.as_of,
    )
