from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.briefr_report import BriefrAttention, BriefrReport
from app.repositories import briefr_report_repo
from app.routers.errors import domain_errors
from app.schemas.briefr import (
    BriefrAgentOut,
    BriefrArchivedIn,
    BriefrItemOut,
    BriefrPlanIn,
    BriefrReadIn,
    BriefrReportDetailOut,
    BriefrReportOut,
)
from app.services import briefr_chef_service, briefr_report_service

# Read and triage only. Reports arrive through scripts/import_briefr_reports.py, which reads the
# agents repository on the server; there is deliberately no endpoint that creates one, so nothing
# outside the tailnet can put text in front of the reader (docs/adr/0044). The one write beyond the
# reader's own state is planning a suggested recipe in listr, which the reader asks for (ADR 0054).
router = APIRouter(prefix="/api/briefr", tags=["briefr"])


def _get_report(db: Session, report_id: int) -> BriefrReport:
    report = briefr_report_repo.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/reports", response_model=list[BriefrReportOut])
def list_reports(
    agent: str | None = Query(default=None, max_length=64),
    attention: BriefrAttention | None = None,
    unread: bool = False,
    archived: bool = False,
    asset_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    reports = briefr_report_repo.list_reports(
        db, agent=agent, attention=attention, unread_only=unread, archived=archived, asset_id=asset_id, limit=limit,
    )
    return [briefr_report_service.report_out(r) for r in reports]


@router.get("/reports/{report_id}", response_model=BriefrReportDetailOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = _get_report(db, report_id)
    states = briefr_chef_service.recipe_states(db, report.items, since=report.run_at.date())
    return briefr_report_service.report_detail_out(report, states)


@router.post("/items/{item_id}/plan", response_model=BriefrItemOut)
def plan_item(item_id: int, payload: BriefrPlanIn, db: Session = Depends(get_db)):
    """Plans a suggested recipe on a day of listr's weekplanner, making it a listr recipe first."""
    item = briefr_report_repo.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    with domain_errors():
        briefr_chef_service.plan_suggestion(db, item, payload.date, replace=payload.replace)
    db.commit()
    states = briefr_chef_service.recipe_states(db, [item], since=item.report.run_at.date())
    return briefr_report_service.item_out(item, states)


@router.put("/reports/{report_id}/read", response_model=BriefrReportOut)
def set_read(report_id: int, payload: BriefrReadIn, db: Session = Depends(get_db)):
    report = _get_report(db, report_id)
    briefr_report_service.set_read(db, report, payload.is_read, now=datetime.now())
    db.commit()
    return briefr_report_service.report_out(report)


@router.put("/reports/{report_id}/archived", response_model=BriefrReportOut)
def set_archived(report_id: int, payload: BriefrArchivedIn, db: Session = Depends(get_db)):
    report = _get_report(db, report_id)
    briefr_report_service.set_archived(db, report, payload.is_archived, now=datetime.now())
    db.commit()
    return briefr_report_service.report_out(report)


@router.get("/agents", response_model=list[BriefrAgentOut])
def list_agents(db: Session = Depends(get_db)):
    return briefr_report_service.list_agents(db)
