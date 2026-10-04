from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gripr_portfolio_link import GriprPortfolioLink


def list_links(db: Session) -> list[GriprPortfolioLink]:
    return list(db.execute(select(GriprPortfolioLink)).scalars().all())


def get_by_account(db: Session, account_id: int) -> GriprPortfolioLink | None:
    query = select(GriprPortfolioLink).where(GriprPortfolioLink.account_id == account_id)
    return db.execute(query).scalar_one_or_none()


def get_by_portfolio(db: Session, portfolio_id: int) -> GriprPortfolioLink | None:
    query = select(GriprPortfolioLink).where(GriprPortfolioLink.portfolio_id == portfolio_id)
    return db.execute(query).scalar_one_or_none()


def create_link(db: Session, account_id: int, portfolio_id: int) -> GriprPortfolioLink:
    link = GriprPortfolioLink(account_id=account_id, portfolio_id=portfolio_id)
    db.add(link)
    db.flush()
    return link


def delete_link(db: Session, link: GriprPortfolioLink) -> None:
    db.delete(link)
    db.flush()
