from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.routers.errors import domain_errors
from app.schemas.portfolio import CashTargetWeightIn, ClosedPositionOut, PositionOut, RebalancePlanOut
from app.services import rebalance_service
from app.services.position_service import position_service
from app.services.target_weight_service import TargetWeightExceeded, set_cash_target_weight

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("", response_model=list[PositionOut])
def list_positions(portfolio_id: int, db: Session = Depends(get_db)):
    return position_service.list_position_rows(db, portfolio_id)


@router.get("/rebalance", response_model=RebalancePlanOut)
def get_rebalance_plan(
    portfolio_id: int,
    amount_eur: Decimal = Query(gt=0, le=Decimal("10000000"), decimal_places=2),
    from_cash: bool = False,
    db: Session = Depends(get_db),
):
    """How to spread `amount_eur` over the holdings below their target, buying only: new money
    (a deposit) or, with `from_cash`, cash already in the portfolio (docs/adr/0041)."""
    with domain_errors():
        return rebalance_service.rebalance_plan(db, portfolio_id, amount_eur, from_cash)


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
