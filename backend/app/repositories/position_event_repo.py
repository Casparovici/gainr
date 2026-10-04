from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.position_event import PositionEvent


def list_events(db: Session, asset_id: int) -> list[PositionEvent]:
    query = select(PositionEvent).where(PositionEvent.asset_id == asset_id).order_by(PositionEvent.date, PositionEvent.id)
    return list(db.execute(query).scalars().all())


def get_event(db: Session, event_id: int) -> PositionEvent | None:
    return db.get(PositionEvent, event_id)


def create_event(db: Session, **fields) -> PositionEvent:
    event = PositionEvent(**fields)
    db.add(event)
    db.flush()
    return event


def update_event(db: Session, event: PositionEvent, **fields) -> PositionEvent:
    # Present key means "apply this", including an explicit None to clear -- callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(event, key, value)
    db.flush()
    return event


def delete_event(db: Session, event: PositionEvent) -> None:
    db.delete(event)
    db.flush()
