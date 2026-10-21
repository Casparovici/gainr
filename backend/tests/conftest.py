import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, configure_sqlite
from app.models import Asset, Portfolio  # noqa: F401  (register all models on Base.metadata)
from app.services.performance_service import performance_service
from app.services.trading212_provider import trading212_provider


@pytest.fixture(autouse=True)
def _reset_performance_cache():
    # performance_service is a module-level singleton with a process-lifetime cache — without
    # this, one test's cached series could leak into another test's (different) in-memory db.
    performance_service.invalidate_cache()
    yield
    performance_service.invalidate_cache()


@pytest.fixture(autouse=True)
def _no_real_trading212(monkeypatch):
    # A developer's backend/.env may hold a real Trading 212 key; no test should ever read the
    # live account with it. Tests that exercise the sync hand in a fake provider instead.
    monkeypatch.setattr(trading212_provider, "api_key", None)
    monkeypatch.setattr(trading212_provider, "api_secret", None)


@pytest.fixture()
def db_session():
    # StaticPool keeps every checkout on the same connection. An in-memory SQLite database
    # belongs to its connection, so without this a second thread — the one TestClient runs the
    # app in — opens a fresh, empty database and finds no tables.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    configure_sqlite(engine)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def portfolio_id(db_session) -> int:
    """Every gainr Transaction requires a portfolio -- one plain portfolio per test, shared by
    everything that test creates, exactly like gripr's tests share one account/category."""
    portfolio = Portfolio(name="Test Portfolio")
    db_session.add(portfolio)
    db_session.flush()
    return portfolio.id
