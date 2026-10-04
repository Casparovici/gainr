from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.listr_category import ListrCategory


def list_categories(db: Session, include_archived: bool = False) -> list[ListrCategory]:
    query = select(ListrCategory).order_by(ListrCategory.sort_order, ListrCategory.name)
    if not include_archived:
        query = query.where(ListrCategory.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_category(db: Session, category_id: int) -> ListrCategory | None:
    return db.get(ListrCategory, category_id)


def get_by_name(db: Session, name: str) -> ListrCategory | None:
    return db.execute(select(ListrCategory).where(ListrCategory.name == name)).scalar_one_or_none()


def next_sort_order(db: Session) -> int:
    current_max = db.execute(select(func.max(ListrCategory.sort_order))).scalar_one_or_none()
    return (current_max or 0) + 1


def create_category(db: Session, **fields) -> ListrCategory:
    category = ListrCategory(**fields)
    db.add(category)
    db.flush()
    return category


def update_category(db: Session, category: ListrCategory, **fields) -> ListrCategory:
    for key, value in fields.items():
        setattr(category, key, value)
    db.flush()
    return category


def reorder(db: Session, category_ids: list[int]) -> None:
    for position, category_id in enumerate(category_ids):
        category = db.get(ListrCategory, category_id)
        if category is not None:
            category.sort_order = position
    db.flush()
