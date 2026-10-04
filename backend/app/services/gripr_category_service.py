from sqlalchemy.orm import Session

from app.models.gripr_category import GriprCategory
from app.repositories import gripr_budget_repo, gripr_category_repo, gripr_transaction_repo


def set_archived(db: Session, category: GriprCategory, is_archived: bool) -> None:
    """Archiving a top-level category takes its subcategories out of view too — a subcategory
    can't meaningfully stay visible once the group it's filed under isn't. Unarchiving only
    restores the category itself; a subcategory archived independently earlier stays archived
    rather than silently reappearing."""
    category.is_archived = is_archived
    if is_archived and category.parent_id is None:
        child_ids = [cid for cid in gripr_category_repo.descendant_ids(db, category.id) if cid != category.id]
        if child_ids:
            gripr_category_repo.bulk_set_archived(db, child_ids, True)
    db.flush()


def delete_category(db: Session, category: GriprCategory) -> None:
    """Deleting a top-level category takes its subcategories with it — one can't meaningfully
    outlive the parent it's filed under. Transactions tagged with any of these categories are
    un-tagged, not deleted: the money movement they record is real and stays in the ledger,
    only the categorization goes away. Budget lines for these categories go too, since a budget
    without a category to attach to is meaningless."""
    category_ids = (
        gripr_category_repo.descendant_ids(db, category.id) if category.parent_id is None else [category.id]
    )
    gripr_transaction_repo.clear_category(db, category_ids)
    gripr_budget_repo.delete_for_categories(db, category_ids)
    gripr_category_repo.delete_categories(db, category_ids)
