"""The rebalance helper on Home: the positions table's values and targets fed through
rebalance.plan (docs/adr/0041 and its addendum).

Only holdings DLT rates Attractive or Neutral can be bought; one rated Critical, or not rated at
all, is left out like one without a target. Left-out holdings still count towards the total, so
every weight stays a share of the whole portfolio. Cash has no rating and keeps its target.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.asset import DltJudgment
from app.schemas.portfolio import PositionOut, RebalanceLeftOutOut, RebalancePlanOut, RebalancePurchaseOut
from app.services.errors import InvalidRequest
from app.services.position_service import CASH_ASSET_ID, position_service
from app.services.rebalance import Bucket, plan

ZERO = Decimal(0)
BUYABLE = frozenset({DltJudgment.ATTRACTIVE, DltJudgment.NEUTRAL})


def _left_out_reason(row: PositionOut) -> str | None:
    """Why a holding gets none of the amount, or None when it can. The rating comes first: a
    Critical holding is left out for that reason whether or not it has a target."""
    if row.asset_id == CASH_ASSET_ID:
        return None if row.target_weight_pct else "no_target"
    if row.dlt_judgment == DltJudgment.CRITICAL:
        return "critical"
    if row.dlt_judgment is None:
        return "unrated"
    if not row.target_weight_pct:
        return "no_target"
    return None


def rebalance_plan(db: Session, portfolio_id: int, amount_eur: Decimal, from_cash: bool) -> RebalancePlanOut:
    rows = position_service.list_position_rows(db, portfolio_id)
    total = sum((r.market_value_eur or ZERO) for r in rows)
    cash = next((r.market_value_eur or ZERO for r in rows if r.asset_id == CASH_ASSET_ID), ZERO)
    if from_cash and amount_eur > cash:
        raise InvalidRequest(f"There's only €{cash:.2f} in cash to invest")

    eligible = [r for r in rows if _left_out_reason(r) is None]
    buckets = [
        Bucket(
            asset_id=r.asset_id,
            value_eur=r.market_value_eur or ZERO,
            target_pct=r.target_weight_pct,
            unit_price_eur=(r.market_value_eur / r.quantity)
            if r.asset_id != CASH_ASSET_ID and r.market_value_eur is not None and r.quantity > ZERO
            else None,
        )
        for r in eligible
    ]
    by_id = {r.asset_id: r for r in rows}
    purchases = [
        RebalancePurchaseOut(
            asset_id=p.asset_id,
            ticker=by_id[p.asset_id].ticker,
            name=by_id[p.asset_id].name,
            dlt_judgment=by_id[p.asset_id].dlt_judgment,
            amount_eur=p.amount_eur,
            quantity=p.quantity,
            weight_before_pct=p.weight_before_pct,
            weight_after_pct=p.weight_after_pct,
            target_pct=p.target_pct,
        )
        for p in plan(buckets, total, amount_eur, from_cash)
    ]
    # Biggest purchase first; what gets nothing (over target) sinks to the bottom.
    purchases.sort(key=lambda p: (p.amount_eur, -(p.weight_before_pct - p.target_pct)), reverse=True)
    left_out = [
        RebalanceLeftOutOut(name=r.name, dlt_judgment=r.dlt_judgment, reason=reason)
        for r in rows
        if r.asset_id != CASH_ASSET_ID and (reason := _left_out_reason(r)) is not None
    ]
    return RebalancePlanOut(
        amount_eur=amount_eur,
        from_cash=from_cash,
        cash_eur=cash,
        purchases=purchases,
        left_out=left_out,
    )
