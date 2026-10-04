from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccount, GriprAccountType


def list_accounts(db: Session, include_archived: bool = False) -> list[GriprAccount]:
    query = select(GriprAccount).order_by(GriprAccount.type, GriprAccount.sort_order, GriprAccount.name)
    if not include_archived:
        query = query.where(GriprAccount.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def next_sort_order(db: Session, type_: GriprAccountType) -> int:
    """New accounts append to the end of their type group rather than jumping to the top."""
    current_max = db.execute(
        select(func.max(GriprAccount.sort_order)).where(GriprAccount.type == type_)
    ).scalar_one_or_none()
    return (current_max or 0) + 1


def reorder(db: Session, account_ids: list[int]) -> None:
    """Assigns sort_order 0..n-1 in the given order. Callers pass the ids of one type group at a
    time — reordering never needs to be globally consistent across groups, only within one."""
    for position, account_id in enumerate(account_ids):
        account = db.get(GriprAccount, account_id)
        if account is not None:
            account.sort_order = position
    db.flush()


def get_account(db: Session, account_id: int) -> GriprAccount | None:
    return db.get(GriprAccount, account_id)


def get_by_name(db: Session, name: str) -> GriprAccount | None:
    return db.execute(select(GriprAccount).where(GriprAccount.name == name)).scalar_one_or_none()


def create_account(db: Session, **fields) -> GriprAccount:
    account = GriprAccount(**fields)
    db.add(account)
    db.flush()
    return account


def update_account(db: Session, account: GriprAccount, **fields) -> GriprAccount:
    # Every key here already passed through the schema's exclude_unset=True, so a field that's
    # present at all — even set to None, e.g. resetting `color` to the derived default — means
    # "apply this", not "skip it".
    for key, value in fields.items():
        setattr(account, key, value)
    db.flush()
    return account


def has_pots(db: Session, account_id: int) -> bool:
    query = select(GriprAccount.id).where(GriprAccount.held_in_account_id == account_id).limit(1)
    return db.execute(query).first() is not None


def pot_parents(db: Session) -> dict[int, int]:
    """{pot account id: the account it sits inside} for every virtual pot."""
    query = select(GriprAccount.id, GriprAccount.held_in_account_id).where(GriprAccount.held_in_account_id.is_not(None))
    return {pot: parent for pot, parent in db.execute(query).all()}
