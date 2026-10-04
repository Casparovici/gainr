from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.position_note_label import PositionNoteLabel


def list_labels(db: Session, include_archived: bool = False) -> list[PositionNoteLabel]:
    query = select(PositionNoteLabel).order_by(PositionNoteLabel.sort_order, PositionNoteLabel.name)
    if not include_archived:
        query = query.where(PositionNoteLabel.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_label(db: Session, label_id: int) -> PositionNoteLabel | None:
    return db.get(PositionNoteLabel, label_id)


def get_by_name(db: Session, name: str) -> PositionNoteLabel | None:
    return db.execute(select(PositionNoteLabel).where(PositionNoteLabel.name == name)).scalar_one_or_none()


def next_sort_order(db: Session) -> int:
    current_max = db.execute(select(func.max(PositionNoteLabel.sort_order))).scalar_one_or_none()
    return (current_max or 0) + 1


def create_label(db: Session, **fields) -> PositionNoteLabel:
    label = PositionNoteLabel(**fields)
    db.add(label)
    db.flush()
    return label


def update_label(db: Session, label: PositionNoteLabel, **fields) -> PositionNoteLabel:
    for key, value in fields.items():
        setattr(label, key, value)
    db.flush()
    return label


def reorder(db: Session, label_ids: list[int]) -> None:
    for position, label_id in enumerate(label_ids):
        label = db.get(PositionNoteLabel, label_id)
        if label is not None:
            label.sort_order = position
    db.flush()


def get_by_ids(db: Session, label_ids: list[int]) -> list[PositionNoteLabel]:
    if not label_ids:
        return []
    return list(db.execute(select(PositionNoteLabel).where(PositionNoteLabel.id.in_(label_ids))).scalars().all())
