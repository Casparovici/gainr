from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, DltJudgment


def list_assets(db: Session) -> list[Asset]:
    return list(db.execute(select(Asset).order_by(Asset.ticker)).scalars().all())


def get_asset(db: Session, asset_id: int) -> Asset | None:
    return db.get(Asset, asset_id)


def get_assets_by_ids(db: Session, asset_ids: list[int]) -> dict[int, Asset]:
    """Every requested asset, keyed by id — one query for a whole positions list rather than
    one lookup per position."""
    if not asset_ids:
        return {}
    rows = db.execute(select(Asset).where(Asset.id.in_(set(asset_ids)))).scalars().all()
    return {asset.id: asset for asset in rows}


def get_by_ticker(db: Session, ticker: str) -> Asset | None:
    return db.execute(select(Asset).where(Asset.ticker == ticker)).scalar_one_or_none()


def create_asset(db: Session, **fields) -> Asset:
    asset = Asset(**fields)
    db.add(asset)
    db.flush()
    return asset


def get_or_create_asset(db: Session, ticker: str, name: str, **fields) -> Asset:
    existing = get_by_ticker(db, ticker)
    if existing:
        return existing
    return create_asset(db, ticker=ticker, name=name, **fields)


def dlt_judgments_by_asset_id(db: Session) -> dict[int, DltJudgment | None]:
    """Every asset's DLT call, keyed by id — one query for the whole positions list rather
    than one lookup per position."""
    rows = db.execute(select(Asset.id, Asset.dlt_judgment)).all()
    return {asset_id: judgment for asset_id, judgment in rows}
