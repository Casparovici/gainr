from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio
from app.repositories import portfolio_repo

MAIN_PORTFOLIO_NAME = "Main"


def list_portfolios(db: Session, include_archived: bool = False) -> list[Portfolio]:
    return portfolio_repo.list_portfolios(db, include_archived=include_archived)


def create_portfolio(db: Session, name: str) -> Portfolio:
    return portfolio_repo.create_portfolio(db, name)


def update_portfolio(db: Session, portfolio: Portfolio, **fields) -> Portfolio:
    return portfolio_repo.update_portfolio(db, portfolio, **fields)


def get_main_portfolio(db: Session) -> Portfolio:
    """The portfolio the gripr bridge (ADR 0014) and the import script default to. Seeded by
    the multi-portfolio migration (ADR 0019); get-or-create here only matters for a from-scratch
    database that's never run that migration (e.g. a fresh test setup using Base.metadata
    directly)."""
    portfolio = portfolio_repo.get_by_name(db, MAIN_PORTFOLIO_NAME)
    if portfolio is not None:
        return portfolio
    return portfolio_repo.create_portfolio(db, MAIN_PORTFOLIO_NAME)
