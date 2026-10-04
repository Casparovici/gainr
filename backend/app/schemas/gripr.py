import re
from datetime import date as date_
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.gripr_account import GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency
from app.models.gripr_transaction import GriprTransactionType


# -- settings -----------------------------------------------------------------------------


class GriprSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start_day: int


class GriprSettingsUpdate(BaseModel):
    # 1-28: every month has a 28th, so a period start day never needs end-of-month fallback
    # logic — see gripr_period_service.
    period_start_day: int = Field(ge=1, le=28)


class GriprPortfolioLinkUpdate(BaseModel):
    # Null unlinks. The account keeps whatever balance it last held rather than reverting to a
    # transaction-derived one, since nothing knows what its pre-link opening balance meant.
    portfolio_id: int | None = None


class GriprPortfolioLinkOut(BaseModel):
    account_id: int
    portfolio_id: int
    balance: Decimal | None = None


# -- accounts -----------------------------------------------------------------------------


class GriprAccountBase(BaseModel):
    name: str
    type: GriprAccountType
    balance_mode: GriprBalanceMode
    opening_balance: Decimal = Decimal(0)
    manual_balance: Decimal = Decimal(0)
    is_archived: bool = False


class GriprAccountCreate(GriprAccountBase):
    pass


class GriprAccountUpdate(BaseModel):
    name: str | None = None
    type: GriprAccountType | None = None
    opening_balance: Decimal | None = None
    manual_balance: Decimal | None = None
    is_archived: bool | None = None
    color: str | None = None
    # A key into gripr_bank_logo_service.GRIPR_BANKS, or null to clear it -- validated against
    # the catalog in the router, since it needs no database lookup but does need that dict.
    bank_logo_key: str | None = None
    # The account this one is a virtual pot inside, or null for a real account.
    held_in_account_id: int | None = None


class GriprAccountOut(GriprAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    balance: Decimal
    # How many transactions this account appears in (either side of a transfer counted) — lets
    # the transaction form's account picker default to the accounts actually used most.
    usage_count: int = 0
    color: str | None = None
    bank_logo_key: str | None = None
    held_in_account_id: int | None = None


class GriprBankLogoOut(BaseModel):
    key: str
    label: str


class GriprAccountReorder(BaseModel):
    # The ids of one type group's accounts, in the desired display order — see
    # gripr_account_repo.reorder for why ordering is always scoped to a single group.
    account_ids: list[int]


# -- categories -----------------------------------------------------------------------------


class GriprCategoryBase(BaseModel):
    name: str
    kind: GriprCategoryKind
    parent_id: int | None = None


class GriprCategoryCreate(GriprCategoryBase):
    pass


class GriprCategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_archived: bool | None = None
    # Only settable on an EXPENSE category, and only to a loan-type account -- enforced in the
    # router, not here, since it needs a database lookup.
    linked_loan_account_id: int | None = None


class GriprCategoryReorder(BaseModel):
    # The ids of one kind's top-level categories, in the desired display order — see
    # gripr_category_repo.reorder.
    category_ids: list[int]


class GriprCategoryOut(GriprCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_archived: bool
    color: str | None = None
    linked_loan_account_id: int | None = None


# -- transactions -----------------------------------------------------------------------------


class GriprTransactionBase(BaseModel):
    date: date_
    type: GriprTransactionType
    amount: Decimal
    account_id: int
    counter_account_id: int | None = None
    category_id: int | None = None
    # Only for type=refund: the expense this money came back for (docs/adr/0023).
    refund_of_id: int | None = None
    notes: str | None = None
    # Only for type=expense: the part fronted for others, and from whom (docs/adr/0032).
    expected_back: Decimal | None = None
    expected_from: str | None = Field(default=None, max_length=80)


class GriprTransactionCreate(GriprTransactionBase):
    pass


class GriprTransactionUpdate(BaseModel):
    date: date_ | None = None
    type: GriprTransactionType | None = None
    amount: Decimal | None = None
    account_id: int | None = None
    counter_account_id: int | None = None
    category_id: int | None = None
    refund_of_id: int | None = None
    notes: str | None = None
    expected_back: Decimal | None = None
    expected_from: str | None = Field(default=None, max_length=80)


class GriprRefundOfOut(BaseModel):
    """Just enough of the linked expense to say what a refund was for."""

    id: int
    date: date_
    amount: Decimal
    account_name: str | None = None
    notes: str | None = None


class GriprTransactionOut(GriprTransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_name: str | None = None
    counter_account_name: str | None = None
    category_name: str | None = None
    # Derived from source_ref, not source_ref itself -- that's an internal id format
    # ("gripr_recurring:<rule id>:<date>") the frontend has no use for.
    is_recurring: bool = False
    # For an expense: how much has come back via refunds linked to it, so the list can show
    # what it really cost. Zero for everything else.
    refunded_amount: Decimal = Decimal(0)
    refund_of: GriprRefundOfOut | None = None
    # For an expense expecting money back: what's still to come (expected minus refunds so far).
    outstanding: Decimal = Decimal(0)


class GriprReceivableOut(BaseModel):
    """An expense with money still to come back -- what the reader is owed for it."""

    id: int
    date: date_
    amount: Decimal
    notes: str | None
    account_name: str | None
    category_name: str | None
    expected_back: Decimal
    expected_from: str | None
    received: Decimal
    outstanding: Decimal


class GriprReceivablesOut(BaseModel):
    total: Decimal
    items: list[GriprReceivableOut]


class GriprTransactionPage(BaseModel):
    items: list[GriprTransactionOut]
    total: int


# -- recurring transactions ----------------------------------------------------------------


class GriprRecurringBase(BaseModel):
    name: str
    type: GriprTransactionType
    amount: Decimal
    account_id: int
    counter_account_id: int | None = None
    category_id: int | None = None
    notes: str | None = None
    frequency: GriprRecurrenceFrequency
    interval: int = Field(default=1, ge=1)
    start_date: date_
    end_date: date_ | None = None


class GriprRecurringCreate(GriprRecurringBase):
    pass


class GriprRecurringUpdate(BaseModel):
    name: str | None = None
    type: GriprTransactionType | None = None
    amount: Decimal | None = None
    account_id: int | None = None
    counter_account_id: int | None = None
    category_id: int | None = None
    notes: str | None = None
    frequency: GriprRecurrenceFrequency | None = None
    interval: int | None = Field(default=None, ge=1)
    start_date: date_ | None = None
    end_date: date_ | None = None
    is_active: bool | None = None


class GriprRecurringOut(GriprRecurringBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    next_due_date: date_
    is_active: bool
    account_name: str | None = None
    counter_account_name: str | None = None
    category_name: str | None = None


class GriprPlannedOccurrenceOut(BaseModel):
    """A recurring rule's occurrence that hasn't been booked yet -- a projection, not a
    transaction, so it has the rule's id rather than one of its own."""

    recurring_id: int
    name: str
    date: date_
    type: GriprTransactionType
    amount: Decimal
    account_id: int
    account_name: str | None = None
    counter_account_id: int | None = None
    counter_account_name: str | None = None
    category_id: int | None = None


class GriprUpcomingRecurringOut(BaseModel):
    until: date_
    items: list[GriprPlannedOccurrenceOut]


# -- budgets -----------------------------------------------------------------------------


class GriprBudgetSet(BaseModel):
    category_id: int
    month: date_
    amount: Decimal


class GriprBudgetLineOut(BaseModel):
    category_id: int
    category_name: str
    kind: GriprCategoryKind
    budgeted: Decimal
    spent: Decimal


class GriprBudgetSuggestionOut(BaseModel):
    category_id: int
    previous_month: Decimal
    year_average: Decimal
    recurring_monthly: Decimal


# -- savings goals --------------------------------------------------------------------------


class GriprSavingsGoalSet(BaseModel):
    account_id: int
    month: date_
    amount: Decimal


class GriprSavingsGoalLineOut(BaseModel):
    account_id: int
    account_name: str
    account_type: GriprAccountType
    budgeted: Decimal
    saved: Decimal


class GriprSavingsGoalSuggestionOut(BaseModel):
    account_id: int
    previous_month: Decimal
    year_average: Decimal
    recurring_monthly: Decimal


# -- overview -----------------------------------------------------------------------------


class GriprMonthTotalOut(BaseModel):
    month: date_
    income: Decimal
    expense: Decimal


class GriprCategoryAmountOut(BaseModel):
    category_id: int
    name: str
    amount: Decimal


class GriprPutAsidePointOut(BaseModel):
    month: date_
    investments: Decimal
    savings: Decimal
    reservations: Decimal


class GriprCategoryTrendPointOut(BaseModel):
    month: date_
    amount: Decimal


class GriprOverviewOut(BaseModel):
    net_worth: Decimal
    money_put_aside: list[GriprPutAsidePointOut]
    income_vs_expense: list[GriprMonthTotalOut]
    spending_by_category: list[GriprCategoryAmountOut]
    budget_status: list[GriprBudgetLineOut]


# -- bank sync (docs/adr/0029) ------------------------------------------------------------


class GriprBankAccountOut(BaseModel):
    iban: str
    product: str
    holder_name: str
    gripr_account_id: int | None
    # False when the latest consent didn't include this account -- its mapping is kept, but
    # nothing syncs from it until a reconnect covers it again.
    in_consent: bool


class GriprBankConnectionOut(BaseModel):
    id: int
    name: str
    # "consent": connected through Enable Banking, renewed by the reader every few months.
    # "api_key": read with a key in the server's environment (Trading 212) -- nothing to connect.
    kind: Literal["consent", "api_key"] = "consent"
    # Sends only date, amount and direction (Trade Republic): its entries are checked against what
    # the reader entered, not categorised from.
    amount_only: bool
    connected: bool
    valid_until: datetime | None
    enabled: bool
    since: date_ | None
    last_synced_at: datetime | None
    last_error: str | None
    accounts: list[GriprBankAccountOut]


class GriprBankRuleOut(BaseModel):
    id: int
    iban: str | None
    text_contains: str | None
    amount: Decimal | None
    amount_max: Decimal | None
    day_of_month: int | None
    direction: Literal["out", "in"] | None
    gripr_account_id: int


class GriprBankStatusOut(BaseModel):
    configured: bool
    connections: list[GriprBankConnectionOut]
    rules: list[GriprBankRuleOut]


class GriprBankConnectionUpdate(BaseModel):
    enabled: bool
    # No date keeps the one already set; switching on for the first time without one starts
    # today -- never reaching back into history the reader entered by hand unless they pick an
    # earlier date on purpose.
    since: date_ | None = None


class GriprBankAccountMappingUpdate(BaseModel):
    # Null skips the account.
    gripr_account_id: int | None = None


class GriprBankRuleCreate(BaseModel):
    iban: str | None = Field(default=None, max_length=42)
    text_contains: str | None = Field(default=None, max_length=80)
    # For a bank that sends amounts only: exactly this amount, optionally around this day of the
    # month (a monthly savings plan).
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    # ...or at most this much (a saveback that varies month to month but has a ceiling).
    amount_max: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    # Only money going out of (or coming into) the synced account; None matches either.
    direction: Literal["out", "in"] | None = None
    gripr_account_id: int

    @field_validator("iban", "text_contains")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("iban")
    @classmethod
    def _iban_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = "".join(value.split()).upper()
        if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{8,30}", compact):
            raise ValueError("not an IBAN")
        return compact

    @model_validator(mode="after")
    def _something_to_match(self) -> "GriprBankRuleCreate":
        has_amount = self.amount is not None or self.amount_max is not None
        if self.iban is None and self.text_contains is None and not has_amount:
            raise ValueError("give an IBAN, a text to look for, or an amount")
        if self.amount is not None and self.amount_max is not None:
            raise ValueError("an amount is either exact or a maximum, not both")
        if self.day_of_month is not None and not has_amount:
            raise ValueError("a day of the month only narrows an amount rule")
        return self


class GriprBankConnectOut(BaseModel):
    url: str


class GriprBankSyncResultOut(BaseModel):
    booked: int
    matched: int
    fulfilled: int
    counterparts: int
    # Bank name -> what went wrong there; the other banks still synced.
    problems: dict[str, str]


class GriprNotificationOut(BaseModel):
    """Something worth telling the reader since their last visit -- see gripr_notification_service."""

    key: str
    kind: Literal["synced", "money_back", "still_owed", "bank"]
    at: datetime
    title: str
    detail: str | None
    link: str
