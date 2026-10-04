from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio


def list_portfolios(db: Session, include_archived: bool = False) -> list[Portfolio]:
    query = select(Portfolio).order_by(Portfolio.sort_order, Portfolio.name)
    if not include_archived:
        query = query.where(Portfolio.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_portfolio(db: Session, portfolio_id: int) -> Portfolio | None:
    return db.get(Portfolio, portfolio_id)


def get_by_name(db: Session, name: str) -> Portfolio | None:
    return db.execute(select(Portfolio).where(Portfolio.name == name)).scalar_one_or_none()


def next_sort_order(db: Session) -> int:
    current_max = db.execute(select(Portfolio.sort_order).order_by(Portfolio.sort_order.desc())).scalars().first()
    return (current_max or 0) + 1


def create_portfolio(db: Session, name: str) -> Portfolio:
    portfolio = Portfolio(name=name, sort_order=next_sort_order(db))
    db.add(portfolio)
    db.flush()
    return portfolio


def update_portfolio(db: Session, portfolio: Portfolio, **fields) -> Portfolio:
    for key, value in fields.items():
        setattr(portfolio, key, value)
    db.flush()
    return portfolio
