"""The rebalance helper's arithmetic: how to spread an amount over the holdings so the portfolio
moves towards its target weights, by buying only (docs/adr/0041). Pure, no database.

Each holding with a target is short of it by (target % of the total after the money is added)
minus what it's worth now. The amount goes to the holdings that are short, in proportion to how
short each is, so the furthest behind gets the most. If the amount covers every shortfall, the
rest is spread over the targets as they stand, keeping them in balance. Nothing is ever sold: a
holding over its target simply gets nothing, and the plan says so rather than hiding it.

Money can be new (a deposit: the total grows by it) or cash already in the portfolio (the total
stays the same and cash shrinks by it). Cash is a bucket like the holdings when it has a target,
so a deposit tops up a cash buffer that's below target, but cash put to work never goes back to
cash.
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

ZERO = Decimal(0)
CENT = Decimal("0.01")
CASH_ID = 0


@dataclass
class Bucket:
    asset_id: int  # CASH_ID for cash
    value_eur: Decimal
    target_pct: Decimal
    # Euros per unit, to turn an amount into a rough number of shares; None for cash or an
    # unpriced holding.
    unit_price_eur: Decimal | None = None


@dataclass
class Purchase:
    asset_id: int
    amount_eur: Decimal
    quantity: Decimal | None
    weight_before_pct: Decimal
    weight_after_pct: Decimal
    target_pct: Decimal


def plan(buckets: list[Bucket], total_value_eur: Decimal, amount_eur: Decimal, from_cash: bool) -> list[Purchase]:
    """One purchase per targeted bucket, amounts in whole cents adding up to `amount_eur` (any
    cents rounding leaves over go to the largest purchase). `total_value_eur` is the whole
    portfolio including holdings without a target, which still count towards the total."""
    if amount_eur <= ZERO or not buckets:
        return []
    total_after = total_value_eur if from_cash else total_value_eur + amount_eur
    if total_after <= ZERO:
        return []

    def value_now(b: Bucket) -> Decimal:
        # Cash put to work leaves the cash bucket before anything is measured.
        return b.value_eur - amount_eur if from_cash and b.asset_id == CASH_ID else b.value_eur

    receiving = [b for b in buckets if not (from_cash and b.asset_id == CASH_ID)]
    shortfalls = {b.asset_id: max(b.target_pct / 100 * total_after - value_now(b), ZERO) for b in receiving}
    short_total = sum(shortfalls.values(), ZERO)
    target_total = sum((b.target_pct for b in receiving), ZERO)

    raw: dict[int, Decimal] = {}
    for b in receiving:
        if short_total >= amount_eur:
            raw[b.asset_id] = amount_eur * shortfalls[b.asset_id] / short_total
        else:
            rest = amount_eur - short_total
            share = b.target_pct / target_total if target_total > ZERO else ZERO
            raw[b.asset_id] = shortfalls[b.asset_id] + rest * share

    amounts = {k: v.quantize(CENT, rounding=ROUND_DOWN) for k, v in raw.items()}
    leftover = amount_eur.quantize(CENT, rounding=ROUND_DOWN) - sum(amounts.values(), ZERO)
    if leftover > ZERO and amounts:
        largest = max(amounts, key=lambda k: raw[k])
        amounts[largest] += leftover

    purchases = []
    for b in buckets:
        before = value_now(b)
        bought = amounts.get(b.asset_id, ZERO)
        purchases.append(
            Purchase(
                asset_id=b.asset_id,
                amount_eur=bought,
                quantity=(bought / b.unit_price_eur) if b.unit_price_eur and b.unit_price_eur > ZERO else None,
                weight_before_pct=b.value_eur / total_value_eur * 100 if total_value_eur > ZERO else ZERO,
                weight_after_pct=(before + bought) / total_after * 100,
                target_pct=b.target_pct,
            )
        )
    return purchases
