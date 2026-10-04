from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.position_note import PositionNote, position_note_assets


def list_notes(db: Session, asset_id: int) -> list[PositionNote]:
    """Every note linked to this position -- including ones that are also about other positions."""
    # id as a tie-breaker: two notes added within the same second (SQLite's CURRENT_TIMESTAMP
    # granularity) would otherwise sort in an unspecified order relative to each other.
    query = (
        select(PositionNote)
        .join(position_note_assets, position_note_assets.c.note_id == PositionNote.id)
        .where(position_note_assets.c.asset_id == asset_id)
        .options(selectinload(PositionNote.assets), selectinload(PositionNote.labels))
        .order_by(PositionNote.created_at.desc(), PositionNote.id.desc())
    )
    return list(db.execute(query).scalars().all())


def list_all_notes(db: Session) -> list[PositionNote]:
    """Every note across every position, newest first -- the Journal tab's source. Eager-loads
    the linked assets (for their ticker/name) and labels so rendering a whole tile grid doesn't
    fire extra queries per note."""
    query = (
        select(PositionNote)
        .options(selectinload(PositionNote.assets), selectinload(PositionNote.labels))
        .order_by(PositionNote.created_at.desc(), PositionNote.id.desc())
    )
    return list(db.execute(query).scalars().all())


def get_note(db: Session, note_id: int) -> PositionNote | None:
    return db.get(PositionNote, note_id)


def is_linked(note: PositionNote, asset_id: int) -> bool:
    return any(a.id == asset_id for a in note.assets)


def create_note(db: Session, **fields) -> PositionNote:
    note = PositionNote(**fields)
    db.add(note)
    db.flush()
    return note


def update_note(db: Session, note: PositionNote, **fields) -> PositionNote:
    # Present key means "apply this", including an explicit None to clear -- callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(note, key, value)
    db.flush()
    return note


def delete_note(db: Session, note: PositionNote) -> None:
    # Its position/label links go with it (SQLAlchemy clears many-to-many association rows).
    db.delete(note)
    db.flush()
