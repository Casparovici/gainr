from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.portfolio import CashTargetWeightIn, ClosedPositionOut, PositionOut
from app.services.position_service import position_service
from app.services.target_weight_service import TargetWeightExceeded, set_cash_target_weight

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("", response_model=list[PositionOut])
def list_positions(portfolio_id: int, db: Session = Depends(get_db)):
    return position_service.list_position_rows(db, portfolio_id)


@router.put("/cash-target-weight", response_model=CashTargetWeightIn)
def update_cash_target_weight(portfolio_id: int, payload: CashTargetWeightIn, db: Session = Depends(get_db)):
    try:
        set_cash_target_weight(db, portfolio_id, payload.target_weight_pct)
    except TargetWeightExceeded as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return payload


@router.get("/closed", response_model=list[ClosedPositionOut])
def list_closed_positions(portfolio_id: int, db: Session = Depends(get_db)):
    _active, closed = position_service.get_positions(db, portfolio_id)
    return [
        ClosedPositionOut(
            asset_id=c.asset_id,
            ticker=c.ticker,
            name=c.name,
            asset_class=c.asset_class,
            total_bought=c.total_bought_eur,
            total_sold=c.total_sold_eur,
            realized_pnl_eur=c.realized_pnl_eur,
            first_buy_date=c.first_buy_date,
            last_sell_date=c.last_sell_date,
        )
        for c in closed
    ]
