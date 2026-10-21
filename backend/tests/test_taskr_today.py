"""Vandaag: today's agenda and what waits in each module, from each module's own data."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.briefr_report import BriefrAttention, BriefrReport
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.models.notr_note import NotrNote
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.models.listr_list import ListrList, ListrListItem
from app.models.listr_meal_plan import ListrMealPlan
from app.models.listr_recipe import ListrRecipe
from app.models.portfolio import Portfolio
from app.models.taskr_task import TaskrTask
from app.routers import taskr as taskr_router
from app.services import gripr_overview_service, taskr_today_service
from app.services.gripr_overview_service import BalanceForecast, BalanceForecastPoint
from app.services.performance_service import performance_service
from tests.test_taskr_agenda import add_plant, add_schedule, add_workout

TODAY = date(2026, 10, 14)


def stub_money_and_returns(monkeypatch, forecast: BalanceForecast | None = None):
    """The portfolio's 1D range and gripr's forecast have tests of their own; here only that
    Vandaag hands them on."""
    calls = []

    def one_day(db, portfolio_id, range_key):
        calls.append((portfolio_id, range_key))
        return {"end_value_eur": Decimal("1000"), "change_eur": Decimal("5"), "change_pct": Decimal("0.5")}

    monkeypatch.setattr(performance_service, "get_range", one_day)
    monkeypatch.setattr(gripr_overview_service, "balance_forecast", lambda db, as_of: forecast or BalanceForecast(points=[]))
    return calls


def test_an_empty_app_has_nothing_waiting(db_session, monkeypatch):
    stub_money_and_returns(monkeypatch)
    db_session.query(Portfolio).delete()

    today = taskr_today_service.build_today(db_session, TODAY)

    assert today.portfolio is None and today.money is None and today.meal is None
    assert today.latest_unread_report is None
    assert today.agenda.overdue == [] and today.agenda.days == []
    assert today.counts.model_dump() == {
        "gripr_uncategorized": 0, "gardnr_due": 0, "trainr_today": 0, "taskr_overdue": 0, "listr_to_get": 0, "briefr_unread": 0,
        "notr_pinned": 0,
    }


def test_each_module_reports_what_waits_today(db_session, monkeypatch):
    stub_money_and_returns(monkeypatch)
    # gardnr: one schedule overdue since last week, trainr: a run today and one tomorrow
    add_schedule(db_session, add_plant(db_session), TODAY - timedelta(days=6))
    add_workout(db_session, TODAY)
    add_workout(db_session, TODAY + timedelta(days=1))
    # taskr: one overdue, one today
    db_session.add_all([TaskrTask(title="Late", due_date=TODAY - timedelta(days=2)), TaskrTask(title="Now", due_date=TODAY)])
    # gripr: two payments to file, one filed, a transfer (never filed)
    checking = GriprAccount(name="ING", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    savings = GriprAccount(name="Sparen", type=GriprAccountType.SAVINGS, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add_all([checking, savings])
    db_session.flush()
    for kind, counter in [(GriprTransactionType.EXPENSE, None), (GriprTransactionType.EXPENSE, None), (GriprTransactionType.TRANSFER, savings.id)]:
        db_session.add(GriprTransaction(date=TODAY, type=kind, amount=Decimal(10), account_id=checking.id, counter_account_id=counter))
    # listr: 3 items on an active list, one ticked; an archived list doesn't count
    category = ListrCategory(name="Groente")
    db_session.add(category)
    db_session.flush()
    items = [ListrItem(name=n, category_id=category.id, default_unit="stuks") for n in ("Appel", "Peer", "Prei")]
    active, archived = ListrList(name="Week"), ListrList(name="Oud", is_archived=True)
    db_session.add_all([*items, active, archived])
    db_session.flush()
    for i, item in enumerate(items):
        db_session.add(ListrListItem(list_id=active.id, grocery_item_id=item.id, unit="stuks", is_checked=i == 0))
    db_session.add(ListrListItem(list_id=archived.id, grocery_item_id=items[0].id, unit="stuks"))
    # briefr: two unread, the newest first; one read
    for i, (title, read) in enumerate([("Old", False), ("Newest", False), ("Read", True)]):
        db_session.add(BriefrReport(
            source_path=f"server/x/{i}", content_hash="h", agent="x", run_at=datetime(2026, 10, 10 + i), title=title,
            body="", attention=BriefrAttention.WATCH, read_at=datetime(2026, 10, 14) if read else None,
        ))
    # notr: two pinned notes (one untitled), one not pinned, one pinned but archived
    db_session.add_all([
        NotrNote(title="Plan", body="x", pinned=True), NotrNote(title="", body="# Ideas\nmore", pinned=True),
        NotrNote(title="Loose", body="x"), NotrNote(title="Done", body="x", pinned=True, is_archived=True),
    ])
    db_session.flush()

    today = taskr_today_service.build_today(db_session, TODAY)

    assert today.counts.model_dump() == {
        "gripr_uncategorized": 2, "gardnr_due": 1, "trainr_today": 1, "taskr_overdue": 1, "listr_to_get": 2, "briefr_unread": 2,
        "notr_pinned": 2,
    }
    # Today's agenda is today only (tomorrow's run waits), with what slipped before it overdue.
    assert [(d.date, sorted(i.title for i in d.items)) for d in today.agenda.days] == [(TODAY, ["Now", "Run"])]
    assert sorted(i.source.value for i in today.agenda.overdue) == ["gardnr", "taskr"]
    assert today.latest_unread_report.title == "Newest"
    assert sorted((n.title, n.preview) for n in today.pinned_notes) == [("", "Ideas"), ("Plan", "x")]


def test_the_chosen_portfolio_and_gripr_money_are_handed_on(db_session, monkeypatch, portfolio_id):
    kids = Portfolio(name="Zeta")
    db_session.add(kids)
    db_session.flush()
    point = BalanceForecastPoint(date=TODAY, balance=Decimal(800), is_forecast=False)
    calls = stub_money_and_returns(
        monkeypatch, BalanceForecast(points=[point], expected_end=Decimal(400), safe_to_move=Decimal(250))
    )

    picked = taskr_today_service.build_today(db_session, TODAY, portfolio_id=kids.id)
    unknown = taskr_today_service.build_today(db_session, TODAY, portfolio_id=9999)

    assert (picked.portfolio.name, picked.portfolio.value_eur, picked.portfolio.day_change_pct) == ("Zeta", Decimal(1000), Decimal("0.5"))
    assert calls[0] == (kids.id, "1D")
    assert unknown.portfolio.portfolio_id != kids.id  # falls back to the first portfolio
    assert (picked.money.safe_to_move_eur, picked.money.expected_end_eur) == (Decimal(250), Decimal(400))


def test_tonights_meal_is_its_recipe_or_its_note(db_session, monkeypatch):
    stub_money_and_returns(monkeypatch)
    recipe = ListrRecipe(title="Pasta pesto")
    db_session.add(recipe)
    db_session.flush()
    db_session.add(ListrMealPlan(date=TODAY, recipe_id=recipe.id))
    db_session.add(ListrMealPlan(date=TODAY + timedelta(days=1), notes="Uit eten"))
    db_session.flush()

    assert taskr_today_service.build_today(db_session, TODAY).meal.title == "Pasta pesto"
    assert taskr_today_service.build_today(db_session, TODAY + timedelta(days=1)).meal.title == "Uit eten"
    assert taskr_today_service.build_today(db_session, TODAY + timedelta(days=2)).meal is None


def test_the_endpoint_answers_for_today(db_session, monkeypatch):
    stub_money_and_returns(monkeypatch)
    app = FastAPI()
    app.include_router(taskr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session

    response = TestClient(app).get("/api/taskr/today")

    assert response.status_code == 200
    assert set(response.json()) >= {"date", "agenda", "portfolio", "money", "meal", "counts", "latest_unread_report"}
