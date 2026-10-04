from sqlalchemy.orm import Session

from app.models.asset_logo import AssetLogo


def get_logo(db: Session, asset_id: int) -> AssetLogo | None:
    return db.get(AssetLogo, asset_id)


def upsert_logo(db: Session, asset_id: int, content_type: str, image: bytes, source_url: str) -> AssetLogo:
    logo = db.get(AssetLogo, asset_id)
    if logo is None:
        logo = AssetLogo(asset_id=asset_id)
        db.add(logo)
    logo.content_type = content_type
    logo.image = image
    logo.source_url = source_url
    db.flush()
    return logo
