from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.briefr_report import BriefrAttention, BriefrReport, BriefrReportItem


def get_report(db: Session, report_id: int) -> BriefrReport | None:
    return db.execute(
        select(BriefrReport).where(BriefrReport.id == report_id).options(selectinload(BriefrReport.items))
    ).scalar_one_or_none()


def get_item(db: Session, item_id: int) -> BriefrReportItem | None:
    return db.get(BriefrReportItem, item_id)


def get_by_source_path(db: Session, source_path: str) -> BriefrReport | None:
    return db.execute(select(BriefrReport).where(BriefrReport.source_path == source_path)).scalar_one_or_none()


def list_reports(
    db: Session,
    *,
    agent: str | None = None,
    attention: BriefrAttention | None = None,
    unread_only: bool = False,
    archived: bool = False,
    asset_id: int | None = None,
    limit: int = 50,
) -> list[BriefrReport]:
    """Newest run first. `archived` picks the archive instead of the inbox, never both. With
    `asset_id`, only reports with a finding about that asset."""
    query = select(BriefrReport).options(selectinload(BriefrReport.items))
    query = query.where(BriefrReport.archived_at.is_not(None) if archived else BriefrReport.archived_at.is_(None))
    if agent is not None:
        query = query.where(BriefrReport.agent == agent)
    if attention is not None:
        query = query.where(BriefrReport.attention == attention)
    if unread_only:
        query = query.where(BriefrReport.read_at.is_(None))
    if asset_id is not None:
        query = query.where(
            BriefrReport.id.in_(select(BriefrReportItem.report_id).where(BriefrReportItem.asset_id == asset_id))
        )
    query = query.order_by(BriefrReport.run_at.desc(), BriefrReport.id.desc()).limit(limit)
    return list(db.execute(query).scalars().all())


def agent_stats(db: Session) -> list[tuple[str, datetime, int, int]]:
    """(agent, last run, reports, unread in the inbox) per agent that ever reported, by name."""
    unread = func.sum(case((BriefrReport.read_at.is_(None) & BriefrReport.archived_at.is_(None), 1), else_=0))
    query = (
        select(BriefrReport.agent, func.max(BriefrReport.run_at), func.count(BriefrReport.id), unread)
        .group_by(BriefrReport.agent)
        .order_by(BriefrReport.agent)
    )
    return [tuple(row) for row in db.execute(query).all()]


def create_report(db: Session, **fields) -> BriefrReport:
    report = BriefrReport(**fields)
    db.add(report)
    db.flush()
    return report


def update_report(db: Session, report: BriefrReport, **fields) -> BriefrReport:
    # Present key means "apply this".
    for key, value in fields.items():
        setattr(report, key, value)
    db.flush()
    return report
