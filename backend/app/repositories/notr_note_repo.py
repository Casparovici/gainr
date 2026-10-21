from datetime import datetime

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.notr_label import notr_note_label_links
from app.models.notr_note import NotrNote, notr_note_assets, notr_note_plants, notr_note_recipes
from app.models.notr_note_image import NotrNoteImage

_LOAD = (
    selectinload(NotrNote.assets),
    selectinload(NotrNote.plants),
    selectinload(NotrNote.recipes),
    selectinload(NotrNote.labels),
)


def _like(text: str) -> str:
    """`text` as a LIKE pattern that matches it literally, anywhere in a value."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_notes(
    db: Session,
    *,
    q: str | None = None,
    label_id: int | None = None,
    asset_id: int | None = None,
    plant_id: int | None = None,
    recipe_id: int | None = None,
    positions_only: bool = False,
    archived: bool = False,
) -> list[NotrNote]:
    """Notes matching every filter given, pinned first and then newest first. Archived notes are
    left out unless `archived` asks for exactly those. Eager-loads the links and labels so a whole
    list renders without extra queries per note."""
    query = select(NotrNote).options(*_LOAD).where(NotrNote.is_archived.is_(archived))
    if q and q.strip():
        pattern = _like(q.strip())
        query = query.where(or_(NotrNote.title.like(pattern, escape="\\"), NotrNote.body.like(pattern, escape="\\")))
    if label_id is not None:
        query = query.where(exists().where(notr_note_label_links.c.note_id == NotrNote.id, notr_note_label_links.c.label_id == label_id))
    if asset_id is not None:
        query = query.where(exists().where(notr_note_assets.c.note_id == NotrNote.id, notr_note_assets.c.asset_id == asset_id))
    if plant_id is not None:
        query = query.where(exists().where(notr_note_plants.c.note_id == NotrNote.id, notr_note_plants.c.plant_id == plant_id))
    if recipe_id is not None:
        query = query.where(exists().where(notr_note_recipes.c.note_id == NotrNote.id, notr_note_recipes.c.recipe_id == recipe_id))
    if positions_only:
        query = query.where(exists().where(notr_note_assets.c.note_id == NotrNote.id))
    # id as a tie-breaker: two notes added within the same second (SQLite's CURRENT_TIMESTAMP
    # granularity) would otherwise sort in an unspecified order relative to each other.
    query = query.order_by(NotrNote.pinned.desc(), NotrNote.created_at.desc(), NotrNote.id.desc())
    return list(db.execute(query).scalars().all())


def pinned_notes(db: Session, limit: int) -> list[NotrNote]:
    query = (
        select(NotrNote)
        .where(NotrNote.pinned.is_(True), NotrNote.is_archived.is_(False))
        .order_by(NotrNote.updated_at.desc(), NotrNote.id.desc())
        .limit(limit)
    )
    return list(db.execute(query).scalars().all())


def count_pinned(db: Session) -> int:
    return db.execute(select(func.count()).select_from(NotrNote).where(NotrNote.pinned.is_(True), NotrNote.is_archived.is_(False))).scalar_one()


def get_note(db: Session, note_id: int) -> NotrNote | None:
    return db.get(NotrNote, note_id)


def create_note(db: Session, **fields) -> NotrNote:
    note = NotrNote(**fields)
    db.add(note)
    db.flush()
    return note


def update_note(db: Session, note: NotrNote, **fields) -> NotrNote:
    # Present key means "apply this", including an explicit None to clear -- callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(note, key, value)
    db.flush()
    return note


def delete_note(db: Session, note: NotrNote) -> None:
    # Its position/plant/recipe/label links go with it (SQLAlchemy clears many-to-many association
    # rows); its pictures are deleted by the service, which knows what a picture is.
    db.delete(note)
    db.flush()


# -- pictures -------------------------------------------------------------------------------


def get_image(db: Session, image_id: int) -> NotrNoteImage | None:
    return db.get(NotrNoteImage, image_id)


def add_image(db: Session, *, content: bytes, content_type: str) -> NotrNoteImage:
    image = NotrNoteImage(content=content, content_type=content_type, size_bytes=len(content))
    db.add(image)
    db.flush()
    return image


def images_of(db: Session, note_id: int) -> list[NotrNoteImage]:
    return list(db.execute(select(NotrNoteImage).where(NotrNoteImage.note_id == note_id)).scalars().all())


def delete_image(db: Session, image: NotrNoteImage) -> None:
    db.delete(image)
    db.flush()


def delete_unclaimed_images_before(db: Session, cutoff: datetime) -> None:
    """Pictures uploaded for a note that was never saved."""
    db.execute(
        delete(NotrNoteImage)
        .where(NotrNoteImage.note_id.is_(None), NotrNoteImage.created_at < cutoff)
        .execution_options(synchronize_session="fetch")
    )
    db.flush()
