from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import portfolio_repo
from app.schemas.portfolio import PortfolioCreate, PortfolioOut, PortfolioUpdate
from app.services import portfolio_service

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


@router.get("", response_model=list[PortfolioOut])
def list_portfolios(include_archived: bool = False, db: Session = Depends(get_db)):
    return portfolio_service.list_portfolios(db, include_archived=include_archived)


@router.post("", response_model=PortfolioOut)
def create_portfolio(payload: PortfolioCreate, db: Session = Depends(get_db)):
    portfolio = portfolio_service.create_portfolio(db, payload.name)
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.put("/{portfolio_id}", response_model=PortfolioOut)
def update_portfolio(portfolio_id: int, payload: PortfolioUpdate, db: Session = Depends(get_db)):
    portfolio = portfolio_repo.get_portfolio(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    portfolio_service.update_portfolio(db, portfolio, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(portfolio)
    return portfolio
