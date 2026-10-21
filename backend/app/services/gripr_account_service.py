from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccount, GriprBalanceMode
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_account_repo, gripr_transaction_repo
from app.services.errors import InvalidRequest, NotFound
from app.services.gripr_bank_logo_service import GRIPR_BANKS


@dataclass
class AccountBalance:
    account: GriprAccount
    balance: Decimal
    usage_count: int = 0


def compute_balance(db: Session, account: GriprAccount) -> Decimal:
    if account.balance_mode == GriprBalanceMode.MANUAL:
        return account.manual_balance

    income = gripr_transaction_repo.sum_amount(db, account.id, GriprTransactionType.INCOME)
    expense = gripr_transaction_repo.sum_amount(db, account.id, GriprTransactionType.EXPENSE)
    # A refund lands in whichever account received it, regardless of which one paid the
    # expense it belongs to -- that's what the bank statement shows too.
    refunded = gripr_transaction_repo.sum_amount(db, account.id, GriprTransactionType.REFUND)
    transferred_out = gripr_transaction_repo.sum_amount(db, account.id, GriprTransactionType.TRANSFER)
    transferred_in = gripr_transaction_repo.sum_amount(
        db, account.id, GriprTransactionType.TRANSFER, counter_side=True
    )
    return account.opening_balance + income - expense + refunded - transferred_out + transferred_in


def list_with_balances(db: Session, include_archived: bool = False) -> list[AccountBalance]:
    accounts = gripr_account_repo.list_accounts(db, include_archived=include_archived)
    usage = gripr_transaction_repo.usage_counts(db)
    return [
        AccountBalance(account=a, balance=compute_balance(db, a), usage_count=usage.get(a.id, 0)) for a in accounts
    ]


def owed_to_you(db: Session) -> Decimal:
    """What the reader fronted and still expects back (docs/adr/0032) -- an asset like the
    Debiteuren account's balance, until it's repaid or written off."""
    from app.services import gripr_receivable_service

    return sum((r.outstanding for r in gripr_receivable_service.list_open(db)), Decimal(0))


def net_worth(db: Session) -> Decimal:
    return sum((ab.balance for ab in list_with_balances(db)), Decimal(0)) + owed_to_you(db)


def update_account(db: Session, account: GriprAccount, fields: dict) -> GriprAccount:
    """A bank icon must be one gripr knows. A pot (`held_in_account_id`) sits inside a real
    account, one level deep: not inside itself or another pot, and an account holding pots can't
    become one (ADR 0029, "Virtual pots")."""
    if fields.get("bank_logo_key") is not None and fields["bank_logo_key"] not in GRIPR_BANKS:
        raise InvalidRequest("Unknown bank_logo_key")
    if fields.get("held_in_account_id") is not None:
        parent = gripr_account_repo.get_account(db, fields["held_in_account_id"])
        if parent is None:
            raise NotFound("Account not found")
        if parent.id == account.id or parent.held_in_account_id is not None or gripr_account_repo.has_pots(db, account.id):
            raise InvalidRequest("A pot sits inside a real account, one level deep")
    return gripr_account_repo.update_account(db, account, **fields)
