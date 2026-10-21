from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories import transaction_repo
from app.services.performance_service import performance_service
from app.services.position_service import cash_balance_by_broker_eur, cash_balance_eur, net_invested_eur, position_service

ZERO = Decimal(0)


class SummaryService:
    def get_summary(self, db: Session, portfolio_id: int) -> dict:
        transactions = transaction_repo.list_all_transactions(db, portfolio_id)
        cash_eur = cash_balance_eur(transactions)
        cash_by_broker_eur = cash_balance_by_broker_eur(transactions)
        invested_eur = net_invested_eur(transactions)

        active, closed = position_service.get_positions_from(transactions)
        holdings_value_eur = ZERO
        unrealized_pnl_eur = ZERO
        # Only positions we could actually value contribute to the unrealized figure, so the
        # percentage below is measured against the cost of those same positions rather than
        # against a cost basis that includes holdings with no price.
        valued_cost_basis_eur = ZERO
        valuations = position_service.valuations(db, active)
        for position in active:
            market_value_eur = valuations[position.asset_id].market_value_eur
            if market_value_eur is None:
                continue
            holdings_value_eur += market_value_eur
            unrealized_pnl_eur += market_value_eur - position.cost_basis_eur
            valued_cost_basis_eur += position.cost_basis_eur

        # Sells against a position that's still open count as realized just as much as ones
        # that closed it out, so both lists feed this.
        realized_pnl_eur = sum((p.realized_pnl_eur for p in active), ZERO) + sum(
            (c.realized_pnl_eur for c in closed), ZERO
        )

        total_value_eur = cash_eur + holdings_value_eur

        ytd = performance_service.get_range(db, portfolio_id, "YTD")
        day = performance_service.get_range(db, portfolio_id, "1D")
        # The same ranges the chart offers, so a tile and the chart's header agree.
        since_start = performance_service.get_range(db, portfolio_id, "Max")
        ytd_return_eur = ytd["change_eur"] if ytd["change_eur"] is not None else ZERO
        ytd_return_pct = ytd["change_pct"]

        total_return_eur = total_value_eur - invested_eur
        total_return_pct = (total_return_eur / invested_eur * 100) if invested_eur > ZERO else None
        unrealized_pnl_pct = (
            (unrealized_pnl_eur / valued_cost_basis_eur * 100) if valued_cost_basis_eur > ZERO else None
        )

        return {
            "total_value_eur": total_value_eur,
            "cash_eur": cash_eur,
            "cash_by_broker_eur": cash_by_broker_eur,
            "holdings_value_eur": holdings_value_eur,
            "ytd_return_eur": ytd_return_eur,
            "ytd_return_pct": ytd_return_pct,
            "ytd_mwr_pct": ytd.get("mwr_pct"),
            "total_mwr_pct": since_start.get("mwr_pct"),
            "total_mwr_yearly_pct": since_start.get("mwr_yearly_pct"),
            "total_return_eur": total_return_eur,
            "total_return_pct": total_return_pct,
            "unrealized_pnl_eur": unrealized_pnl_eur,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "realized_pnl_eur": realized_pnl_eur,
            "total_invested_eur": invested_eur,
            "day_change_eur": day["change_eur"],
            "day_change_pct": day["change_pct"],
            "as_of": date.today(),
        }


summary_service = SummaryService()
