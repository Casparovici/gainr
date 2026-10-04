from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.listr_recipe_category import ListrRecipeCategory


def list_categories(db: Session, include_archived: bool = False) -> list[ListrRecipeCategory]:
    query = select(ListrRecipeCategory).order_by(ListrRecipeCategory.sort_order, ListrRecipeCategory.name)
    if not include_archived:
        query = query.where(ListrRecipeCategory.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_category(db: Session, category_id: int) -> ListrRecipeCategory | None:
    return db.get(ListrRecipeCategory, category_id)


def get_by_name(db: Session, name: str) -> ListrRecipeCategory | None:
    return db.execute(
        select(ListrRecipeCategory).where(ListrRecipeCategory.name == name)
    ).scalar_one_or_none()


def next_sort_order(db: Session) -> int:
    current_max = db.execute(select(func.max(ListrRecipeCategory.sort_order))).scalar_one_or_none()
    return (current_max or 0) + 1


def create_category(db: Session, **fields) -> ListrRecipeCategory:
    category = ListrRecipeCategory(**fields)
    db.add(category)
    db.flush()
    return category


def update_category(db: Session, category: ListrRecipeCategory, **fields) -> ListrRecipeCategory:
    for key, value in fields.items():
        setattr(category, key, value)
    db.flush()
    return category


def reorder(db: Session, category_ids: list[int]) -> None:
    for position, category_id in enumerate(category_ids):
        category = db.get(ListrRecipeCategory, category_id)
        if category is not None:
            category.sort_order = position
    db.flush()


def get_by_ids(db: Session, category_ids: list[int]) -> list[ListrRecipeCategory]:
    if not category_ids:
        return []
    return list(
        db.execute(select(ListrRecipeCategory).where(ListrRecipeCategory.id.in_(category_ids))).scalars().all()
    )
