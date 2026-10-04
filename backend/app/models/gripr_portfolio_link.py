from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GriprPortfolioLink(Base):
    """Bridges one gripr account to one gainr portfolio -- see docs/adr/0014 and docs/adr/0021.
    Both sides are unique: an account mirrors at most one portfolio, and a portfolio is mirrored
    by at most one account, so a transfer touching a linked account always resolves to exactly
    one gainr side to book against."""

    __tablename__ = "pefi_portfolio_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("pefi_accounts.id"), unique=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), unique=True)
