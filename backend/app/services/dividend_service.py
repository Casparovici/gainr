"""The Income page: dividend_income's ledger arithmetic, joined with the holdings' names, cost
basis and market value for the yields (docs/adr/0041)."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories import transaction_repo
from app.schemas.portfolio import DividendHoldingOut, DividendIncomeOut, DividendMonthOut, DividendYearOut
from app.services.dividend_income import MONTHS_AHEAD, MONTHS_BACK, add_months, dividend_income, percent_of
from app.services.position_service import position_service

ZERO = Decimal(0)


def get_income(db: Session, portfolio_id: int, today: date) -> DividendIncomeOut:
    transactions = transaction_repo.list_all_transactions(db, portfolio_id)
    income = dividend_income(transactions, today)
    active, _closed = position_service.get_positions_from(transactions)
    valuations = position_service.valuations(db, active)
    open_by_id = {p.asset_id: p for p in active}
    assets = {t.asset_id: t.asset for t in transactions if t.asset_id is not None and t.asset is not None}

    holdings = []
    for asset_id, h in income.holdings.items():
        asset = assets.get(asset_id)
        if asset is None:
            continue
        position = open_by_id.get(asset_id)
        market_value = valuations[asset_id].market_value_eur if position else None
        holdings.append(
            DividendHoldingOut(
                asset_id=asset_id,
                ticker=asset.ticker,
                name=asset.name,
                is_held=position is not None,
                received_total_eur=h.received_total_eur,
                received_12m_eur=h.received_12m_eur,
                payments_12m=h.payments_12m,
                expected_12m_eur=h.expected_12m_eur,
                last_paid_on=h.last_paid_on,
                yield_on_cost_pct=percent_of(h.expected_12m_eur, position.cost_basis_eur) if position else None,
                current_yield_pct=percent_of(h.expected_12m_eur, market_value),
            )
        )
    # What the coming year rests on first, then what was received.
    holdings.sort(key=lambda h: (h.expected_12m_eur, h.received_12m_eur, h.received_total_eur), reverse=True)

    this_month = (today.year, today.month)
    months = []
    for offset in range(-(MONTHS_BACK - 1), MONTHS_AHEAD + 1):
        year, month = add_months(this_month, offset)
        months.append(
            DividendMonthOut(
                month=f"{year:04d}-{month:02d}",
                received_eur=income.received_by_month.get((year, month), ZERO) if offset <= 0 else ZERO,
                expected_eur=income.expected_by_month.get((year, month), ZERO) if offset >= 0 else ZERO,
            )
        )

    years_seen = sorted({y for y, _ in income.received_by_month}, reverse=True)
    years = [
        DividendYearOut(
            year=year,
            total_eur=sum((v for (y, _), v in income.received_by_month.items() if y == year), ZERO),
            months=[income.received_by_month.get((year, m), ZERO) for m in range(1, 13)],
        )
        for year in years_seen
    ]

    expected = sum((h.expected_12m_eur for h in holdings), ZERO)
    paying = [p for p in active if income.holdings.get(p.asset_id) is not None]
    holdings_value = sum((valuations[p.asset_id].market_value_eur or ZERO) for p in active)
    holdings_cost = sum((p.cost_basis_eur for p in active), ZERO)
    by_year = {y.year: y.total_eur for y in years}
    return DividendIncomeOut(
        as_of=today,
        received_this_year_eur=by_year.get(today.year, ZERO),
        received_last_year_eur=by_year.get(today.year - 1, ZERO),
        received_12m_eur=sum((h.received_12m_eur for h in holdings), ZERO),
        expected_12m_eur=expected,
        paying_holdings=len(paying),
        yield_on_cost_pct=percent_of(expected, holdings_cost),
        current_yield_pct=percent_of(expected, holdings_value),
        months=months,
        years=years,
        holdings=holdings,
    )
