from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notr_label import NotrLabel


def list_labels(db: Session, include_archived: bool = False) -> list[NotrLabel]:
    query = select(NotrLabel).order_by(NotrLabel.sort_order, NotrLabel.name)
    if not include_archived:
        query = query.where(NotrLabel.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_label(db: Session, label_id: int) -> NotrLabel | None:
    return db.get(NotrLabel, label_id)


def get_by_name(db: Session, name: str) -> NotrLabel | None:
    return db.execute(select(NotrLabel).where(NotrLabel.name == name)).scalar_one_or_none()


def next_sort_order(db: Session) -> int:
    current_max = db.execute(select(func.max(NotrLabel.sort_order))).scalar_one_or_none()
    return (current_max or 0) + 1


def create_label(db: Session, **fields) -> NotrLabel:
    label = NotrLabel(**fields)
    db.add(label)
    db.flush()
    return label


def update_label(db: Session, label: NotrLabel, **fields) -> NotrLabel:
    for key, value in fields.items():
        setattr(label, key, value)
    db.flush()
    return label


def reorder(db: Session, label_ids: list[int]) -> None:
    for position, label_id in enumerate(label_ids):
        label = db.get(NotrLabel, label_id)
        if label is not None:
            label.sort_order = position
    db.flush()


def get_by_ids(db: Session, label_ids: list[int]) -> list[NotrLabel]:
    if not label_ids:
        return []
    return list(db.execute(select(NotrLabel).where(NotrLabel.id.in_(label_ids))).scalars().all())
