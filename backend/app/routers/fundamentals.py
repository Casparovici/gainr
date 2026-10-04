from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import asset_repo
from app.schemas.fundamentals import FinancialsOut, NewsOut, NewsSourcesUpdate
from app.services import news_sources
from app.services.fundamentals_service import fundamentals_service

router = APIRouter(prefix="/api/assets", tags=["fundamentals"])
# Not under /api/assets: "/news-sources/catalog" would otherwise have to be ordered ahead of
# every "/{asset_id}/..." route to avoid being read as an asset id.
catalog_router = APIRouter(prefix="/api/news-sources", tags=["fundamentals"])


@catalog_router.get("/catalog")
def get_news_source_catalog():
    """Everything a position can pull extra news from: market feeds, sectors, industries."""
    return news_sources.catalog()


def _asset(db: Session, asset_id: int):
    asset = asset_repo.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/news", response_model=NewsOut)
def get_asset_news(asset_id: int, db: Session = Depends(get_db)):
    """Stories about the company from the past week. Empty is a normal answer."""
    return fundamentals_service.get_news(db, _asset(db, asset_id))


@router.get("/{asset_id}/financials", response_model=FinancialsOut)
def get_asset_financials(asset_id: int, db: Session = Depends(get_db)):
    """Reported revenue, growth, free cash flow and net income, plus a valuation/quality
    snapshot (P/E, margins, leverage, dividend). Empty for anything that doesn't file
    statements — an ETF or a currency pair has none."""
    return fundamentals_service.get_financials(db, _asset(db, asset_id))


@router.put("/{asset_id}/news-sources", response_model=NewsOut)
def update_news_sources(asset_id: int, payload: NewsSourcesUpdate, db: Session = Depends(get_db)):
    """Replaces the position's extra news sources and returns its news with them applied."""
    asset = _asset(db, asset_id)
    try:
        fundamentals_service.set_news_sources(db, asset, payload.sources)
    except news_sources.InvalidNewsSource as e:
        raise HTTPException(status_code=400, detail=str(e))
    news = fundamentals_service.get_news(db, asset)
    db.commit()
    return news
