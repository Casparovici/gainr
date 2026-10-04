from datetime import date as date_
from datetime import datetime

from pydantic import BaseModel


class BrokerUnmappedOut(BaseModel):
    """An instrument the broker has records for that no asset has the ISIN of -- held back until
    the reader links one."""

    isin: str
    ticker: str
    name: str
    currency: str
    records: int
    first_date: date_


class BrokerStatusOut(BaseModel):
    # A Trading 212 API key is set on this server; without one nothing here can work.
    configured: bool
    enabled: bool
    since: date_ | None
    portfolio_id: int | None
    last_synced_at: datetime | None
    last_error: str | None
    unmapped: list[BrokerUnmappedOut]


class BrokerSettingsUpdate(BaseModel):
    enabled: bool
    # No date keeps the one already set; switching on for the first time without one starts
    # today -- never reaching back into history entered by hand unless picked on purpose.
    since: date_ | None = None
    # The portfolio its records book into; required the first time it's switched on.
    portfolio_id: int | None = None


class BrokerSyncResultOut(BaseModel):
    booked: int
    matched: int
    deposits: int
    unmapped: list[BrokerUnmappedOut]
    problems: list[str]


class NotificationOut(BaseModel):
    """Something worth telling the reader since their last visit -- see gainr_notification_service."""

    key: str
    kind: str
    at: datetime
    title: str
    detail: str | None
    link: str
