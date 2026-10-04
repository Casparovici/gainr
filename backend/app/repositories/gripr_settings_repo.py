from sqlalchemy.orm import Session

from app.models.gripr_settings import SETTINGS_ID, GriprSettings


def get(db: Session) -> GriprSettings | None:
    return db.get(GriprSettings, SETTINGS_ID)


def get_period_start_day(db: Session) -> int:
    settings = get(db)
    return settings.period_start_day if settings else 1


def set_period_start_day(db: Session, value: int) -> GriprSettings:
    settings = _get_or_create(db)
    settings.period_start_day = value
    db.flush()
    return settings


def _get_or_create(db: Session) -> GriprSettings:
    settings = get(db)
    if settings is None:
        settings = GriprSettings(id=SETTINGS_ID)
        db.add(settings)
    return settings
