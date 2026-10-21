"""Vandaag, the app's start screen: what needs the reader today, gathered from every module
(docs/adr/0048). Like taskr's agenda it stores nothing and owns nothing -- each figure comes from
the module that owns it, through that module's own services and repositories, on every request.
taskr hosts it because taskr already is the cross-module agenda; the agenda part is exactly
`taskr_agenda_service.build_agenda` for today.

Nothing here sums across gainr portfolios: the portfolio shown is the one the reader has picked
(or the first one), as everywhere else in gainr (docs/adr/0019)."""

from datetime import date as date_

from sqlalchemy.orm import Session

from app.repositories import (
    briefr_report_repo,
    gripr_transaction_repo,
    listr_list_repo,
    listr_meal_plan_repo,
    notr_note_repo,
    portfolio_repo,
)
from app.schemas.taskr import (
    AgendaOut,
    AgendaSource,
    TodayCountsOut,
    TodayMealOut,
    TodayMoneyOut,
    TodayOut,
    TodayPortfolioOut,
    TodayReportOut,
)
from app.services import gripr_overview_service, notr_note_service, taskr_agenda_service
from app.services.performance_service import performance_service

# More unread reports than this reads as "lots"; the count stops there rather than load them all.
UNREAD_CAP = 99
# Vandaag lists this many pinned notes; the rest are a tap away in notr.
PINNED_NOTES_SHOWN = 5


def build_today(db: Session, today: date_, portfolio_id: int | None = None) -> TodayOut:
    agenda = taskr_agenda_service.build_agenda(db, today, today, today)
    unread = briefr_report_repo.list_reports(db, unread_only=True, limit=UNREAD_CAP)
    latest = unread[0] if unread else None
    return TodayOut(
        date=today,
        agenda=agenda,
        portfolio=_portfolio(db, portfolio_id),
        money=_money(db, today),
        latest_unread_report=(
            TodayReportOut(id=latest.id, title=latest.title, attention=latest.attention.value) if latest else None
        ),
        meal=_meal(db, today),
        pinned_notes=notr_note_service.pinned_for_today(db, PINNED_NOTES_SHOWN),
        counts=_counts(db, agenda, today, len(unread)),
    )


def _portfolio(db: Session, portfolio_id: int | None) -> TodayPortfolioOut | None:
    portfolios = portfolio_repo.list_portfolios(db)
    chosen = next((p for p in portfolios if p.id == portfolio_id), portfolios[0] if portfolios else None)
    if chosen is None:
        return None
    day = performance_service.get_range(db, chosen.id, "1D")
    return TodayPortfolioOut(
        portfolio_id=chosen.id,
        name=chosen.name,
        value_eur=day["end_value_eur"],
        day_change_eur=day["change_eur"],
        day_change_pct=day["change_pct"],
    )


def _money(db: Session, today: date_) -> TodayMoneyOut | None:
    forecast = gripr_overview_service.balance_forecast(db, as_of=today)
    if not forecast.points:  # no checking account to forecast
        return None
    return TodayMoneyOut(safe_to_move_eur=forecast.safe_to_move, expected_end_eur=forecast.expected_end)


def _meal(db: Session, today: date_) -> TodayMealOut | None:
    plan = listr_meal_plan_repo.get_by_date(db, today)
    if plan is None:
        return None
    title = plan.recipe.title if plan.recipe else plan.leftover.name if plan.leftover else plan.notes
    if not title:
        return None
    return TodayMealOut(title=title, is_cooked=plan.is_cooked)


def _counts(db: Session, agenda: AgendaOut, today: date_, briefr_unread: int) -> TodayCountsOut:
    items = agenda.overdue + [item for day in agenda.days for item in day.items]
    _uncategorized, uncategorized_total = gripr_transaction_repo.list_transactions(db, limit=1, uncategorized=True)
    active_lists = {grocery_list.id for grocery_list in listr_list_repo.list_lists(db)}
    to_get = sum(total - checked for list_id, (total, checked) in listr_list_repo.counts_by_list(db).items() if list_id in active_lists)
    return TodayCountsOut(
        gripr_uncategorized=uncategorized_total,
        gardnr_due=sum(1 for i in items if i.source == AgendaSource.GARDNR),
        trainr_today=sum(1 for i in items if i.source == AgendaSource.TRAINR and i.due_date == today),
        taskr_overdue=sum(1 for i in agenda.overdue if i.source == AgendaSource.TASKR),
        listr_to_get=to_get,
        briefr_unread=briefr_unread,
        notr_pinned=notr_note_repo.count_pinned(db),
    )
