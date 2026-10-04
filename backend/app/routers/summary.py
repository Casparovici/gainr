from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.portfolio import SummaryOut
from app.services.summary_service import summary_service

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=SummaryOut)
def get_summary(portfolio_id: int, db: Session = Depends(get_db)):
    return summary_service.get_summary(db, portfolio_id)
