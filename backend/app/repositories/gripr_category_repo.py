from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.gripr_category import GriprCategory, GriprCategoryKind


def list_categories(db: Session, include_archived: bool = False) -> list[GriprCategory]:
    query = select(GriprCategory).order_by(GriprCategory.kind, GriprCategory.sort_order, GriprCategory.name)
    if not include_archived:
        query = query.where(GriprCategory.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def next_sort_order(db: Session, kind: GriprCategoryKind) -> int:
    """New top-level categories append to the end of their kind group. Subcategories aren't
    independently orderable, so this is never called for them."""
    current_max = db.execute(
        select(func.max(GriprCategory.sort_order)).where(
            GriprCategory.kind == kind, GriprCategory.parent_id.is_(None)
        )
    ).scalar_one_or_none()
    return (current_max or 0) + 1


def reorder(db: Session, category_ids: list[int]) -> None:
    """Assigns sort_order 0..n-1 in the given order — same contract as the account reorder:
    callers pass one kind's top-level ids at a time."""
    for position, category_id in enumerate(category_ids):
        category = db.get(GriprCategory, category_id)
        if category is not None:
            category.sort_order = position
    db.flush()


def update_category(db: Session, category: GriprCategory, **fields) -> GriprCategory:
    # Every key here already passed through the schema's exclude_unset=True, so a field that's
    # present at all — even set to None, e.g. resetting `color` to the derived default — means
    # "apply this", not "skip it". (Previously this skipped None unconditionally, silently
    # no-opping the colour-reset "×" button.)
    for key, value in fields.items():
        setattr(category, key, value)
    db.flush()
    return category


def get_category(db: Session, category_id: int) -> GriprCategory | None:
    return db.get(GriprCategory, category_id)


def get_by_name(db: Session, name: str, kind: GriprCategoryKind, parent_id: int | None) -> GriprCategory | None:
    query = select(GriprCategory).where(
        GriprCategory.name == name, GriprCategory.kind == kind, GriprCategory.parent_id == parent_id
    )
    return db.execute(query).scalar_one_or_none()


def descendant_ids(db: Session, category_id: int) -> list[int]:
    """A top-level category plus every subcategory under it — what a budget's "spent" figure
    needs to sum over, since transactions can be tagged at either level."""
    children = db.execute(select(GriprCategory.id).where(GriprCategory.parent_id == category_id)).scalars().all()
    return [category_id, *children]


def create_category(db: Session, **fields) -> GriprCategory:
    category = GriprCategory(**fields)
    db.add(category)
    db.flush()
    return category


def bulk_set_archived(db: Session, category_ids: list[int], is_archived: bool) -> None:
    db.execute(update(GriprCategory).where(GriprCategory.id.in_(category_ids)).values(is_archived=is_archived))
    db.flush()


def delete_categories(db: Session, category_ids: list[int]) -> None:
    db.execute(delete(GriprCategory).where(GriprCategory.id.in_(category_ids)))
    db.flush()
