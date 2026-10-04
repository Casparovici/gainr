from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import asset_repo, position_event_repo
from app.schemas.calendar import CalendarEventOut, PositionCalendarOut, PositionEventCreate, PositionEventUpdate
from app.services.calendar_service import calendar_service, manual_event_out

router = APIRouter(prefix="/api/assets", tags=["calendar"])


def _asset(db: Session, asset_id: int):
    asset = asset_repo.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/calendar", response_model=PositionCalendarOut)
def get_position_calendar(asset_id: int, db: Session = Depends(get_db)):
    """Upcoming earnings/dividend dates and the user's own events, plus past results."""
    calendar = calendar_service.get_calendar(db, _asset(db, asset_id))
    db.commit()  # persists a freshly fetched cache row
    return calendar


@router.post("/{asset_id}/events", response_model=CalendarEventOut)
def create_position_event(asset_id: int, payload: PositionEventCreate, db: Session = Depends(get_db)):
    _asset(db, asset_id)
    event = position_event_repo.create_event(db, asset_id=asset_id, **payload.model_dump())
    db.commit()
    db.refresh(event)
    return manual_event_out(event)


def _event(db: Session, asset_id: int, event_id: int):
    event = position_event_repo.get_event(db, event_id)
    if event is None or event.asset_id != asset_id:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put("/{asset_id}/events/{event_id}", response_model=CalendarEventOut)
def update_position_event(asset_id: int, event_id: int, payload: PositionEventUpdate, db: Session = Depends(get_db)):
    event = _event(db, asset_id, event_id)
    fields = payload.model_dump(exclude_unset=True)
    # date/kind/title can't be cleared, only changed; notes can be.
    for required in ("date", "kind", "title"):
        if required in fields and fields[required] is None:
            raise HTTPException(status_code=400, detail=f"{required} can't be empty")
    position_event_repo.update_event(db, event, **fields)
    db.commit()
    db.refresh(event)
    return manual_event_out(event)


@router.delete("/{asset_id}/events/{event_id}", status_code=204)
def delete_position_event(asset_id: int, event_id: int, db: Session = Depends(get_db)):
    position_event_repo.delete_event(db, _event(db, asset_id, event_id))
    db.commit()
