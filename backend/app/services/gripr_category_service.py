from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccountType
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.repositories import (
    gripr_account_repo,
    gripr_budget_repo,
    gripr_category_repo,
    gripr_recurring_repo,
    gripr_transaction_repo,
)
from app.services.errors import InvalidRequest


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
    only the categorization goes away. Recurring rules filed under them likewise keep running,
    uncategorised. Budget lines for these categories go too, since a budget without a category
    to attach to is meaningless."""
    category_ids = (
        gripr_category_repo.descendant_ids(db, category.id) if category.parent_id is None else [category.id]
    )
    gripr_transaction_repo.clear_category(db, category_ids)
    gripr_recurring_repo.clear_category(db, category_ids)
    gripr_budget_repo.delete_for_categories(db, category_ids)
    gripr_category_repo.delete_categories(db, category_ids)


def update_category(db: Session, category: GriprCategory, fields: dict) -> GriprCategory:
    """Only an expense category links to a loan, and only to a loan account (ADR 0003). Archiving
    goes through set_archived, so a top-level category takes its subcategories along."""
    is_archived = fields.pop("is_archived", None)
    if fields.get("linked_loan_account_id") is not None:
        if category.kind != GriprCategoryKind.EXPENSE:
            raise InvalidRequest("Only an expense category can link to a loan account")
        loan = gripr_account_repo.get_account(db, fields["linked_loan_account_id"])
        if loan is None or loan.type != GriprAccountType.LOAN:
            raise InvalidRequest("linked_loan_account_id must reference a loan account")
    if fields:
        gripr_category_repo.update_category(db, category, **fields)
    if is_archived is not None:
        set_archived(db, category, is_archived)
    return category
