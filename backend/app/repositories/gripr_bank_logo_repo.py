from sqlalchemy.orm import Session

from app.models.gripr_bank_logo import GriprBankLogo


def get_logo(db: Session, key: str) -> GriprBankLogo | None:
    return db.get(GriprBankLogo, key)


def upsert_logo(db: Session, key: str, content_type: str, image: bytes, source_url: str) -> GriprBankLogo:
    logo = db.get(GriprBankLogo, key)
    if logo is None:
        logo = GriprBankLogo(key=key)
        db.add(logo)
    logo.content_type = content_type
    logo.image = image
    logo.source_url = source_url
    db.flush()
    return logo
