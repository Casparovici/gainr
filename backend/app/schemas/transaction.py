from datetime import date as date_, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.transaction import TransactionType


class TransactionBase(BaseModel):
    date: date_
    type: TransactionType
    portfolio_id: int
    asset_id: int | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    local_value: Decimal | None = None
    fx_rate: Decimal | None = None
    value_eur: Decimal = Decimal(0)
    costs: Decimal = Decimal(0)
    total_eur: Decimal = Decimal(0)
    broker: str | None = None
    to_broker: str | None = None  # only set for a Transfer -- the destination broker
    notes: str | None = None


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    date: date_ | None = None
    type: TransactionType | None = None
    portfolio_id: int | None = None
    asset_id: int | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    local_value: Decimal | None = None
    fx_rate: Decimal | None = None
    value_eur: Decimal | None = None
    costs: Decimal | None = None
    total_eur: Decimal | None = None
    broker: str | None = None
    to_broker: str | None = None
    notes: str | None = None


class TransactionOut(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str | None = None
    asset_name: str | None = None
    native_currency: str | None = None  # currency `price`/`local_value` are denominated in
    attachment_count: int = 0


class TransactionAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
