from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.asset_snapshot import AssetSnapshot


def get_fresh(db: Session, asset_id: int, kind: str, max_age: timedelta) -> AssetSnapshot | None:
    """The cached snapshot, or None once it's older than `max_age`."""
    snapshot = db.get(AssetSnapshot, (asset_id, kind))
    if snapshot is None:
        return None
    return snapshot if datetime.now() - snapshot.fetched_at < max_age else None


def upsert(db: Session, asset_id: int, kind: str, payload: str) -> AssetSnapshot:
    snapshot = db.get(AssetSnapshot, (asset_id, kind))
    if snapshot is None:
        snapshot = AssetSnapshot(asset_id=asset_id, kind=kind)
        db.add(snapshot)
    snapshot.payload = payload
    snapshot.fetched_at = datetime.now()
    db.flush()
    return snapshot
