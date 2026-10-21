from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.portfolio import DividendIncomeOut
from app.services import dividend_service

router = APIRouter(prefix="/api/income", tags=["income"])


@router.get("/dividends", response_model=DividendIncomeOut)
def get_dividend_income(portfolio_id: int, db: Session = Depends(get_db)):
    return dividend_service.get_income(db, portfolio_id, today=date.today())
