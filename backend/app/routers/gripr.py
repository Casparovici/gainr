import csv
import hashlib
import io
import logging
from datetime import date as date_
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.gripr_account import GriprAccountType
from app.models.gripr_category import GriprCategoryKind
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import (
    bank_sync_repo,
    gripr_account_repo,
    gripr_category_repo,
    gripr_portfolio_link_repo,
    gripr_recurring_repo,
    gripr_settings_repo,
    gripr_transaction_repo,
)
from app.schemas.gripr import (
    GriprBankAccountMappingUpdate,
    GriprBankAccountOut,
    GriprBankConnectionOut,
    GriprBankConnectionUpdate,
    GriprBankConnectOut,
    GriprBankRuleCreate,
    GriprBankRuleOut,
    GriprBankStatusOut,
    GriprBankSyncResultOut,
    GriprAccountCreate,
    GriprAccountOut,
    GriprAccountReorder,
    GriprAccountUpdate,
    GriprBankLogoOut,
    GriprBudgetLineOut,
    GriprBudgetSet,
    GriprBudgetSuggestionOut,
    GriprCategoryCreate,
    GriprCategoryOut,
    GriprCategoryReorder,
    GriprCategoryTrendPointOut,
    GriprCategoryUpdate,
    GriprOverviewOut,
    GriprPortfolioLinkOut,
    GriprPortfolioLinkUpdate,
    GriprRecurringCreate,
    GriprPlannedOccurrenceOut,
    GriprRecurringOut,
    GriprNotificationOut,
    GriprReceivableOut,
    GriprReceivablesOut,
    GriprUpcomingRecurringOut,
    GriprRecurringUpdate,
    GriprRefundOfOut,
    GriprSavingsGoalLineOut,
    GriprSavingsGoalSet,
    GriprSavingsGoalSuggestionOut,
    GriprSettingsOut,
    GriprSettingsUpdate,
    GriprTransactionCreate,
    GriprTransactionOut,
    GriprTransactionPage,
    GriprTransactionUpdate,
)
from app.services import (
    bank_sync_service,
    gripr_account_service,
    gripr_budget_service,
    gripr_category_service,
    gripr_overview_service,
    gripr_portfolio_link_service,
    gripr_notification_service,
    gripr_receivable_service,
    gripr_recurring_service,
    gripr_transaction_service,
)
from app.services.enablebanking_provider import EnableBankingError
from app.services.gripr_bank_logo_service import GRIPR_BANKS, gripr_bank_logo_service

# Logos are stable, unchanging brand icons once fetched -- no reason for a browser to ever
# re-ask, unlike prices/balances which change daily. Same header gainr's asset logos use.
LOGO_CACHE_CONTROL = "no-cache"

router = APIRouter(prefix="/api/gripr", tags=["gripr"])
logger = logging.getLogger(__name__)


# -- settings -----------------------------------------------------------------------------


@router.get("/settings", response_model=GriprSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return GriprSettingsOut(period_start_day=gripr_settings_repo.get_period_start_day(db))


@router.put("/settings", response_model=GriprSettingsOut)
def update_settings(payload: GriprSettingsUpdate, db: Session = Depends(get_db)):
    gripr_settings_repo.set_period_start_day(db, payload.period_start_day)
    db.commit()
    return GriprSettingsOut(period_start_day=payload.period_start_day)


@router.get("/portfolio-links", response_model=list[GriprPortfolioLinkOut])
def list_portfolio_links(db: Session = Depends(get_db)):
    return [
        GriprPortfolioLinkOut(account_id=link.account_id, portfolio_id=link.portfolio_id)
        for link in gripr_portfolio_link_repo.list_links(db)
    ]


@router.put("/portfolio-links/{account_id}", response_model=GriprPortfolioLinkOut | None)
def update_portfolio_link(account_id: int, payload: GriprPortfolioLinkUpdate, db: Session = Depends(get_db)):
    """Points `account_id` at a gainr portfolio (or unlinks it), then immediately writes that
    account's balance so linking shows its effect straight away."""
    if gripr_account_repo.get_account(db, account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    try:
        link = gripr_portfolio_link_service.set_link(db, account_id, payload.portfolio_id)
    except gripr_portfolio_link_service.PortfolioAlreadyLinkedError:
        raise HTTPException(status_code=409, detail="That portfolio already mirrors a different account")
    balances = gripr_portfolio_link_service.sync_balance(db)
    db.commit()
    if link is None:
        return None
    return GriprPortfolioLinkOut(account_id=link.account_id, portfolio_id=link.portfolio_id, balance=balances.get(account_id))


@router.post("/portfolio-links/sync", response_model=list[GriprPortfolioLinkOut])
def sync_portfolio_links(db: Session = Depends(get_db)):
    """Re-reads every linked portfolio's value onto its account now, rather than waiting for the
    daily run — market movement changes this figure without anything in gripr happening."""
    balances = gripr_portfolio_link_service.sync_balance(db)
    db.commit()
    return [
        GriprPortfolioLinkOut(account_id=link.account_id, portfolio_id=link.portfolio_id, balance=balances.get(link.account_id))
        for link in gripr_portfolio_link_repo.list_links(db)
    ]


# -- bank sync (docs/adr/0029) ------------------------------------------------------------


def _utc(value: datetime | None) -> datetime | None:
    # Stored naive in UTC; sent with the zone so the browser shows its own local time.
    return value.replace(tzinfo=timezone.utc) if value is not None else None


def _bank_status(db: Session) -> GriprBankStatusOut:
    accounts = bank_sync_repo.list_accounts(db)
    return GriprBankStatusOut(
        configured=bank_sync_service.is_configured(),
        connections=[
            GriprBankConnectionOut(
                id=c.id,
                name=c.aspsp_name,
                kind="api_key" if c.provider == bank_sync_service.TRADING212 else "consent",
                amount_only=c.amount_only,
                connected=bank_sync_service.is_connected(c),
                valid_until=_utc(c.valid_until),
                enabled=c.enabled,
                since=c.since,
                last_synced_at=_utc(c.last_synced_at),
                last_error=c.last_error,
                accounts=[
                    GriprBankAccountOut(
                        iban=a.iban,
                        product=a.product,
                        holder_name=a.holder_name,
                        gripr_account_id=a.gripr_account_id,
                        in_consent=a.eb_uid is not None or c.provider == bank_sync_service.TRADING212,
                    )
                    for a in accounts
                    if a.connection_id == c.id
                ],
            )
            for c in bank_sync_repo.list_connections(db)
        ],
        rules=[
            GriprBankRuleOut(
                id=r.id, iban=r.iban, text_contains=r.text_contains, amount=r.amount, amount_max=r.amount_max,
                day_of_month=r.day_of_month, direction=r.direction, gripr_account_id=r.gripr_account_id,
            )
            for r in bank_sync_repo.list_rules(db)
        ],
    )


def _connection_or_404(db: Session, connection_id: int):
    connection = bank_sync_repo.get_connection(db, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Bank not found")
    return connection


@router.get("/banks", response_model=GriprBankStatusOut)
def bank_status(db: Session = Depends(get_db)):
    return _bank_status(db)


@router.put("/banks/accounts/{iban}", response_model=GriprBankStatusOut)
def update_bank_account(iban: str, payload: GriprBankAccountMappingUpdate, db: Session = Depends(get_db)):
    account = bank_sync_repo.get_account(db, iban)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    if payload.gripr_account_id is not None and gripr_account_repo.get_account(db, payload.gripr_account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    account.gripr_account_id = payload.gripr_account_id
    db.commit()
    return _bank_status(db)


@router.post("/banks/rules", response_model=GriprBankStatusOut)
def create_bank_rule(payload: GriprBankRuleCreate, db: Session = Depends(get_db)):
    if gripr_account_repo.get_account(db, payload.gripr_account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    bank_sync_repo.create_rule(
        db, iban=payload.iban, text_contains=payload.text_contains, amount=payload.amount, amount_max=payload.amount_max,
        day_of_month=payload.day_of_month, direction=payload.direction, gripr_account_id=payload.gripr_account_id,
    )
    db.commit()
    return _bank_status(db)


@router.delete("/banks/rules/{rule_id}", response_model=GriprBankStatusOut)
def delete_bank_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = bank_sync_repo.get_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    bank_sync_repo.delete_rule(db, rule)
    db.commit()
    return _bank_status(db)


@router.post("/banks/sync", response_model=GriprBankSyncResultOut)
def run_bank_sync(db: Session = Depends(get_db)):
    """Syncs every switched-on bank now. A bank that can't be read is reported in `problems`
    rather than failing the others."""
    result = bank_sync_service.sync(db)
    db.commit()
    return GriprBankSyncResultOut(
        booked=result.booked, matched=result.matched, fulfilled=result.fulfilled,
        counterparts=result.counterparts, problems=result.problems,
    )


@router.put("/banks/{connection_id}", response_model=GriprBankStatusOut)
def update_bank_connection(connection_id: int, payload: GriprBankConnectionUpdate, db: Session = Depends(get_db)):
    connection = _connection_or_404(db, connection_id)
    since = payload.since or connection.since
    if payload.enabled and since is None:
        since = date_.today()
    bank_sync_repo.update_connection(db, connection, enabled=payload.enabled, since=since)
    db.commit()
    return _bank_status(db)


@router.post("/banks/{connection_id}/connect", response_model=GriprBankConnectOut)
def start_bank_connect(connection_id: int, db: Session = Depends(get_db)):
    """Starts a consent at that bank; the frontend sends the reader to the returned URL."""
    connection = _connection_or_404(db, connection_id)
    if connection.provider == bank_sync_service.TRADING212:
        raise HTTPException(status_code=409, detail="Trading 212 is read with the API key set on the server; there's nothing to connect")
    try:
        url = bank_sync_service.start_connect(db, connection)
    except bank_sync_service.BankNotConfigured as exc:
        raise HTTPException(status_code=409, detail="Bank connections aren't configured on this server") from exc
    except EnableBankingError as exc:
        # The reader sees a generic message; what Enable Banking actually said goes to the log.
        logger.warning("Starting a %s consent failed: %s", connection.aspsp_name, exc)
        raise HTTPException(status_code=502, detail="Enable Banking didn't accept the request") from exc
    db.commit()
    return GriprBankConnectOut(url=url)


@router.delete("/banks/{connection_id}/connection", response_model=GriprBankStatusOut)
def disconnect_bank(connection_id: int, db: Session = Depends(get_db)):
    bank_sync_service.disconnect(db, _connection_or_404(db, connection_id))
    db.commit()
    return _bank_status(db)


# The redirect URL registered with Enable Banking, from when ING was the only bank -- it now
# finishes every bank's consent (the state says which).
@router.get("/ing/callback", include_in_schema=False)
def bank_callback(state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
    """Where a bank (via Enable Banking) sends the reader back after the consent. Always ends on
    the Accounts page; the query string says how it went, never echoing what the bank sent."""
    if error or not code:
        return RedirectResponse("/gripr?bank=cancelled", status_code=303)
    try:
        bank_sync_service.complete_connect(db, state, code)
    except bank_sync_service.BankStateMismatch:
        return RedirectResponse("/gripr?bank=failed", status_code=303)
    except EnableBankingError as exc:
        logger.warning("Finishing a bank consent failed: %s", exc)
        db.rollback()
        return RedirectResponse("/gripr?bank=failed", status_code=303)
    db.commit()
    return RedirectResponse("/gripr?bank=connected", status_code=303)


def _to_account_out(account, balance, usage_count: int = 0) -> GriprAccountOut:
    return GriprAccountOut(
        id=account.id,
        name=account.name,
        type=account.type,
        balance_mode=account.balance_mode,
        opening_balance=account.opening_balance,
        manual_balance=account.manual_balance,
        is_archived=account.is_archived,
        balance=balance,
        usage_count=usage_count,
        color=account.color,
        bank_logo_key=account.bank_logo_key,
        held_in_account_id=account.held_in_account_id,
    )


# -- accounts -----------------------------------------------------------------------------


@router.get("/accounts", response_model=list[GriprAccountOut])
def list_accounts(include_archived: bool = False, db: Session = Depends(get_db)):
    # There's no live scheduler for recurring transactions, so the Accounts page — the first
    # thing gripr loads — is what catches balances up on whatever's come due since it was last
    # opened, the same opportunistic-on-read pattern gainr already uses for price refreshes.
    gripr_recurring_service.generate_due(db)
    balances = gripr_account_service.list_with_balances(db, include_archived=include_archived)
    return [_to_account_out(ab.account, ab.balance, ab.usage_count) for ab in balances]


@router.post("/accounts", response_model=GriprAccountOut)
def create_account(payload: GriprAccountCreate, db: Session = Depends(get_db)):
    sort_order = gripr_account_repo.next_sort_order(db, payload.type)
    account = gripr_account_repo.create_account(db, **payload.model_dump(), sort_order=sort_order)
    db.commit()
    return _to_account_out(account, gripr_account_service.compute_balance(db, account))


@router.put("/accounts/reorder", status_code=204)
def reorder_accounts(payload: GriprAccountReorder, db: Session = Depends(get_db)):
    gripr_account_repo.reorder(db, payload.account_ids)
    db.commit()


@router.put("/accounts/{account_id}", response_model=GriprAccountOut)
def update_account(account_id: int, payload: GriprAccountUpdate, db: Session = Depends(get_db)):
    account = gripr_account_repo.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("bank_logo_key") is not None and fields["bank_logo_key"] not in GRIPR_BANKS:
        raise HTTPException(status_code=400, detail="Unknown bank_logo_key")
    if fields.get("held_in_account_id") is not None:
        parent = gripr_account_repo.get_account(db, fields["held_in_account_id"])
        if parent is None:
            raise HTTPException(status_code=404, detail="Account not found")
        # One level only: a pot sits in a real account, and an account holding pots isn't one.
        if parent.id == account.id or parent.held_in_account_id is not None or gripr_account_repo.has_pots(db, account.id):
            raise HTTPException(status_code=400, detail="A pot sits inside a real account, one level deep")
    gripr_account_repo.update_account(db, account, **fields)
    db.commit()
    return _to_account_out(account, gripr_account_service.compute_balance(db, account))


@router.get("/bank-logos", response_model=list[GriprBankLogoOut])
def list_bank_logos():
    return [GriprBankLogoOut(key=key, label=bank["label"]) for key, bank in GRIPR_BANKS.items()]


@router.get("/bank-logos/{key}/logo")
def get_bank_logo(key: str, request: Request, db: Session = Depends(get_db)):
    """A catalog entry's brand icon as raw image bytes, or 404 -- same shape as
    GET /api/assets/{id}/logo, served from our own origin rather than the bank's."""
    logo = gripr_bank_logo_service.get_logo(db, key)
    db.commit()
    if logo is None:
        return Response(status_code=404, headers={"Cache-Control": LOGO_CACHE_CONTROL})

    etag = f'"{hashlib.sha1(logo.image).hexdigest()}"'
    headers = {"Cache-Control": LOGO_CACHE_CONTROL, "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=logo.image, media_type=logo.content_type, headers=headers)


# -- categories -----------------------------------------------------------------------------


@router.get("/categories", response_model=list[GriprCategoryOut])
def list_categories(include_archived: bool = False, db: Session = Depends(get_db)):
    return gripr_category_repo.list_categories(db, include_archived=include_archived)


@router.post("/categories", response_model=GriprCategoryOut)
def create_category(payload: GriprCategoryCreate, db: Session = Depends(get_db)):
    fields = payload.model_dump()
    if fields["parent_id"] is None:
        fields["sort_order"] = gripr_category_repo.next_sort_order(db, payload.kind)
    category = gripr_category_repo.create_category(db, **fields)
    db.commit()
    return category


@router.put("/categories/reorder", status_code=204)
def reorder_categories(payload: GriprCategoryReorder, db: Session = Depends(get_db)):
    gripr_category_repo.reorder(db, payload.category_ids)
    db.commit()


@router.put("/categories/{category_id}", response_model=GriprCategoryOut)
def update_category(category_id: int, payload: GriprCategoryUpdate, db: Session = Depends(get_db)):
    category = gripr_category_repo.get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    fields = payload.model_dump(exclude_unset=True)
    is_archived = fields.pop("is_archived", None)

    if "linked_loan_account_id" in fields and fields["linked_loan_account_id"] is not None:
        if category.kind != GriprCategoryKind.EXPENSE:
            raise HTTPException(status_code=400, detail="Only an expense category can link to a loan account")
        linked_account = gripr_account_repo.get_account(db, fields["linked_loan_account_id"])
        if linked_account is None or linked_account.type != GriprAccountType.LOAN:
            raise HTTPException(status_code=400, detail="linked_loan_account_id must reference a loan account")

    if fields:
        gripr_category_repo.update_category(db, category, **fields)
    if is_archived is not None:
        gripr_category_service.set_archived(db, category, is_archived)
    db.commit()
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = gripr_category_repo.get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    gripr_category_service.delete_category(db, category)
    db.commit()


# -- transactions -----------------------------------------------------------------------------

GRIPR_CSV_COLUMNS = ["date", "type", "account", "counter_account", "category", "amount", "notes"]


def _to_txn_out(txn, refunded_amount: Decimal = Decimal(0)) -> GriprTransactionOut:
    original = txn.refund_of
    return GriprTransactionOut(
        id=txn.id,
        date=txn.date,
        type=txn.type,
        amount=txn.amount,
        account_id=txn.account_id,
        counter_account_id=txn.counter_account_id,
        category_id=txn.category_id,
        refund_of_id=txn.refund_of_id,
        notes=txn.notes,
        expected_back=txn.expected_back,
        expected_from=txn.expected_from,
        outstanding=gripr_receivable_service.outstanding_for(txn, refunded_amount),
        account_name=txn.account.name if txn.account else None,
        counter_account_name=txn.counter_account.name if txn.counter_account else None,
        category_name=txn.category.name if txn.category else None,
        is_recurring=txn.source_ref is not None and txn.source_ref.startswith("pefi_recurring:"),
        refunded_amount=refunded_amount,
        refund_of=GriprRefundOfOut(
            id=original.id, date=original.date, amount=original.amount,
            account_name=original.account.name if original.account else None, notes=original.notes,
        ) if original is not None else None,
    )


def _single_txn_out(db: Session, txn) -> GriprTransactionOut:
    refunded = gripr_transaction_repo.refunded_totals(db, [txn.id]).get(txn.id, Decimal(0))
    return _to_txn_out(txn, refunded)


@router.get("/transactions/export.csv")
def export_transactions_csv(db: Session = Depends(get_db)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(GRIPR_CSV_COLUMNS)
    for txn in gripr_transaction_repo.list_all_transactions(db):
        writer.writerow(
            [
                txn.date.isoformat(),
                txn.type.value,
                txn.account.name if txn.account else "",
                txn.counter_account.name if txn.counter_account else "",
                txn.category.name if txn.category else "",
                txn.amount,
                txn.notes,
            ]
        )
    buffer.seek(0)
    filename = f"gripr-transactions-{date_.today().isoformat()}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/transactions", response_model=GriprTransactionPage)
def list_transactions(
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "date",
    sort_dir: str = "desc",
    account_id: int | None = None,
    category_id: int | None = None,
    txn_type: GriprTransactionType | None = Query(default=None, alias="type"),
    date_from: date_ | None = None,
    date_to: date_ | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    uncategorized: bool = False,
    db: Session = Depends(get_db),
):
    # A parent category rolls up its subcategories, the same way the budget page's "spent"
    # figure does — picking "Groceries" should surface everything filed under it, not just
    # transactions tagged at the top level.
    category_ids = gripr_category_repo.descendant_ids(db, category_id) if category_id is not None else None
    items, total = gripr_transaction_repo.list_transactions(
        db,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        account_id=account_id,
        category_ids=category_ids,
        type_filter=txn_type,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        uncategorized=uncategorized,
    )
    refunded = gripr_transaction_repo.refunded_totals(
        db, [t.id for t in items if t.type == GriprTransactionType.EXPENSE]
    )
    return GriprTransactionPage(
        items=[_to_txn_out(t, refunded.get(t.id, Decimal(0))) for t in items], total=total
    )


@router.post("/transactions", response_model=GriprTransactionOut)
def create_transaction(payload: GriprTransactionCreate, db: Session = Depends(get_db)):
    if payload.amount < 0:
        raise HTTPException(status_code=400, detail="amount must be a positive magnitude")
    try:
        txn = gripr_transaction_service.create_transaction(db, **payload.model_dump())
    except gripr_transaction_service.InvalidRefundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(txn)
    return _single_txn_out(db, txn)


@router.put("/transactions/{transaction_id}", response_model=GriprTransactionOut)
def update_transaction(transaction_id: int, payload: GriprTransactionUpdate, db: Session = Depends(get_db)):
    if payload.amount is not None and payload.amount < 0:
        raise HTTPException(status_code=400, detail="amount must be a positive magnitude")
    txn = gripr_transaction_repo.get_transaction(db, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        gripr_transaction_service.update_transaction(db, txn, **payload.model_dump(exclude_unset=True))
    except gripr_transaction_service.InvalidRefundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(txn)
    return _single_txn_out(db, txn)


# -- notifications -------------------------------------------------------------------------

# A first visit on a device (nothing seen yet) looks back this far.
NOTIFICATIONS_FIRST_LOOK = timedelta(days=7)


@router.get("/notifications", response_model=list[GriprNotificationOut])
def list_notifications(since: datetime | None = None, db: Session = Depends(get_db)):
    """What's new since `since` (when this device last opened the bell), plus standing reminders,
    newest first."""
    now = datetime.now(timezone.utc)
    if since is None:
        since = now - NOTIFICATIONS_FIRST_LOOK
    elif since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return [GriprNotificationOut(**vars(n)) for n in gripr_notification_service.list_notifications(db, since, now)]


# -- money owed back (docs/adr/0032) -------------------------------------------------------


def _receivables_out(db: Session) -> GriprReceivablesOut:
    items = [
        GriprReceivableOut(
            id=r.expense.id, date=r.expense.date, amount=r.expense.amount, notes=r.expense.notes,
            account_name=r.expense.account.name if r.expense.account else None,
            category_name=r.expense.category.name if r.expense.category else None,
            expected_back=r.expected, expected_from=r.expense.expected_from,
            received=r.received, outstanding=r.outstanding,
        )
        for r in gripr_receivable_service.list_open(db)
    ]
    return GriprReceivablesOut(total=sum((i.outstanding for i in items), Decimal(0)), items=items)


@router.get("/receivables", response_model=GriprReceivablesOut)
def list_receivables(db: Session = Depends(get_db)):
    """Expenses with money still to come back, oldest first, and the total owed."""
    return _receivables_out(db)


@router.post("/receivables/{transaction_id}/write-off", response_model=GriprReceivablesOut)
def write_off_receivable(transaction_id: int, db: Session = Depends(get_db)):
    """Stops expecting the rest of this expense back; it counts as the reader's own spending."""
    txn = gripr_transaction_repo.get_transaction(db, transaction_id)
    if txn is None or txn.expected_back is None:
        raise HTTPException(status_code=404, detail="Nothing is expected back for this transaction")
    gripr_receivable_service.write_off(db, txn)
    db.commit()
    return _receivables_out(db)


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    txn = gripr_transaction_repo.get_transaction(db, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    gripr_transaction_service.delete_transaction(db, txn)
    db.commit()


# -- recurring transactions ----------------------------------------------------------------


def _to_recurring_out(rule) -> GriprRecurringOut:
    return GriprRecurringOut(
        id=rule.id,
        name=rule.name,
        type=rule.type,
        amount=rule.amount,
        account_id=rule.account_id,
        counter_account_id=rule.counter_account_id,
        category_id=rule.category_id,
        notes=rule.notes,
        frequency=rule.frequency,
        interval=rule.interval,
        start_date=rule.start_date,
        end_date=rule.end_date,
        next_due_date=rule.next_due_date,
        is_active=rule.is_active,
        account_name=rule.account.name if rule.account else None,
        counter_account_name=rule.counter_account.name if rule.counter_account else None,
        category_name=rule.category.name if rule.category else None,
    )


def _check_recurring_refund(db: Session, type_: GriprTransactionType, category_id: int | None) -> None:
    """Rejects a refund rule the transactions it generates couldn't be booked with."""
    if type_ != GriprTransactionType.REFUND:
        return
    try:
        gripr_transaction_service.ensure_refund_category(db, category_id)
    except gripr_transaction_service.InvalidRefundError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recurring", response_model=list[GriprRecurringOut])
def list_recurring(include_inactive: bool = True, db: Session = Depends(get_db)):
    gripr_recurring_service.generate_due(db)
    rules = gripr_recurring_repo.list_recurring(db, include_inactive=include_inactive)
    return [_to_recurring_out(r) for r in rules]


@router.get("/recurring/upcoming", response_model=GriprUpcomingRecurringOut)
def upcoming_recurring(db: Session = Depends(get_db)):
    """What active rules will still book from tomorrow through the end of the current period --
    projected, not booked (see gripr_recurring_service.planned_occurrences). Occurrences
    already in the ledger come through the transactions list instead."""
    gripr_recurring_service.generate_due(db)
    until, planned = gripr_recurring_service.planned_until_period_end(db, gripr_settings_repo.get_period_start_day(db))
    return GriprUpcomingRecurringOut(
        until=until,
        items=[
            GriprPlannedOccurrenceOut(
                recurring_id=p.rule.id,
                name=p.rule.name,
                date=p.date,
                type=p.rule.type,
                amount=p.rule.amount,
                account_id=p.rule.account_id,
                account_name=p.rule.account.name if p.rule.account else None,
                counter_account_id=p.rule.counter_account_id,
                counter_account_name=p.rule.counter_account.name if p.rule.counter_account else None,
                category_id=p.rule.category_id,
            )
            for p in planned
        ],
    )


@router.post("/recurring", response_model=GriprRecurringOut)
def create_recurring(payload: GriprRecurringCreate, db: Session = Depends(get_db)):
    if payload.amount < 0:
        raise HTTPException(status_code=400, detail="amount must be a positive magnitude")
    _check_recurring_refund(db, payload.type, payload.category_id)
    rule = gripr_recurring_repo.create_recurring(
        db, **payload.model_dump(), next_due_date=payload.start_date
    )
    db.commit()
    db.refresh(rule)
    return _to_recurring_out(rule)


@router.put("/recurring/{recurring_id}", response_model=GriprRecurringOut)
def update_recurring(recurring_id: int, payload: GriprRecurringUpdate, db: Session = Depends(get_db)):
    if payload.amount is not None and payload.amount < 0:
        raise HTTPException(status_code=400, detail="amount must be a positive magnitude")
    rule = gripr_recurring_repo.get_recurring(db, recurring_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    fields = payload.model_dump(exclude_unset=True)
    _check_recurring_refund(db, fields.get("type", rule.type), fields.get("category_id", rule.category_id))
    gripr_recurring_service.update_recurring(db, rule, **fields)
    db.commit()
    db.refresh(rule)
    return _to_recurring_out(rule)


@router.delete("/recurring/{recurring_id}", status_code=204)
def delete_recurring(recurring_id: int, db: Session = Depends(get_db)):
    rule = gripr_recurring_repo.get_recurring(db, recurring_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    gripr_recurring_repo.delete_recurring(db, rule)
    db.commit()


# -- budgets -----------------------------------------------------------------------------


@router.get("/budgets", response_model=list[GriprBudgetLineOut])
def get_budgets(month: date_, db: Session = Depends(get_db)):
    lines = gripr_budget_service.get_budget_status(db, month)
    return [
        GriprBudgetLineOut(
            category_id=line.category.id, category_name=line.category.name, kind=line.category.kind,
            budgeted=line.budgeted, spent=line.spent,
        )
        for line in lines
    ]


@router.put("/budgets", response_model=GriprBudgetLineOut)
def set_budget(payload: GriprBudgetSet, db: Session = Depends(get_db)):
    category = gripr_category_repo.get_category(db, payload.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    gripr_budget_service.set_budget(db, payload.category_id, payload.month, payload.amount)
    db.commit()
    lines = gripr_budget_service.get_budget_status(db, payload.month)
    line = next(line for line in lines if line.category.id == payload.category_id)
    return GriprBudgetLineOut(
        category_id=line.category.id, category_name=line.category.name, kind=line.category.kind,
        budgeted=line.budgeted, spent=line.spent,
    )


@router.get("/budgets/suggestions", response_model=list[GriprBudgetSuggestionOut])
def get_budget_suggestions(month: date_, db: Session = Depends(get_db)):
    return [
        GriprBudgetSuggestionOut(
            category_id=s.category_id,
            previous_month=s.previous_month,
            year_average=s.year_average,
            recurring_monthly=s.recurring_monthly,
        )
        for s in gripr_budget_service.get_suggestions(db, month)
    ]


# -- savings goals -------------------------------------------------------------------------


def _to_savings_goal_line_out(line) -> GriprSavingsGoalLineOut:
    return GriprSavingsGoalLineOut(
        account_id=line.account.id,
        account_name=line.account.name,
        account_type=line.account.type,
        budgeted=line.budgeted,
        saved=line.saved,
    )


@router.get("/savings-goals", response_model=list[GriprSavingsGoalLineOut])
def get_savings_goals(month: date_, db: Session = Depends(get_db)):
    lines = gripr_budget_service.get_savings_status(db, month)
    return [_to_savings_goal_line_out(line) for line in lines]


@router.put("/savings-goals", response_model=GriprSavingsGoalLineOut)
def set_savings_goal(payload: GriprSavingsGoalSet, db: Session = Depends(get_db)):
    account = gripr_account_repo.get_account(db, payload.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.type not in gripr_budget_service.SAVINGS_GOAL_ACCOUNT_TYPES:
        raise HTTPException(status_code=400, detail="A savings goal must target a savings or investment account")
    gripr_budget_service.set_savings_goal(db, payload.account_id, payload.month, payload.amount)
    db.commit()
    lines = gripr_budget_service.get_savings_status(db, payload.month)
    line = next(line for line in lines if line.account.id == payload.account_id)
    return _to_savings_goal_line_out(line)


@router.get("/savings-goals/suggestions", response_model=list[GriprSavingsGoalSuggestionOut])
def get_savings_goal_suggestions(month: date_, db: Session = Depends(get_db)):
    return [
        GriprSavingsGoalSuggestionOut(
            account_id=s.account_id,
            previous_month=s.previous_month,
            year_average=s.year_average,
            recurring_monthly=s.recurring_monthly,
        )
        for s in gripr_budget_service.get_savings_suggestions(db, month)
    ]


# -- overview -----------------------------------------------------------------------------


@router.get("/overview", response_model=GriprOverviewOut)
def get_overview(month: date_ | None = None, months: int = 12, db: Session = Depends(get_db)):
    month = month or date_.today()
    budget_lines = gripr_budget_service.get_budget_status(db, month)
    return GriprOverviewOut(
        net_worth=gripr_account_service.net_worth(db),
        money_put_aside=[vars(p) for p in gripr_overview_service.money_put_aside(db, months=months, as_of=month)],
        income_vs_expense=[
            {"month": m.month, "income": m.income, "expense": m.expense}
            for m in gripr_overview_service.income_vs_expense(db, months=months, as_of=month)
        ],
        spending_by_category=[
            {"category_id": c.category_id, "name": c.name, "amount": c.amount}
            for c in gripr_overview_service.spending_by_category(db, month)
        ],
        budget_status=[
            {
                "category_id": line.category.id,
                "category_name": line.category.name,
                "kind": line.category.kind,
                "budgeted": line.budgeted,
                "spent": line.spent,
            }
            for line in budget_lines
        ],
    )


@router.get("/overview/category-trend", response_model=list[GriprCategoryTrendPointOut])
def get_category_trend(
    category_id: int, month: date_ | None = None, months: int = 12, db: Session = Depends(get_db)
):
    month = month or date_.today()
    return [
        {"month": p.month, "amount": p.amount}
        for p in gripr_overview_service.category_trend(db, category_id, months=months, as_of=month)
    ]
