"""Enforces the one rule spanning both places a target weight can be set: every holding's
target (plus cash's, which lives in `portfolio_settings` since cash has no `Asset` row) must
never sum past 100% *within one portfolio* -- a target is a portfolio's own allocation judgment,
not the asset's (see docs/adr/0019). Centralized here so the asset-target and cash-target-weight
endpoints can't drift into two different implementations of the same check. See docs/adr/0002.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories import asset_repo, portfolio_asset_target_repo, portfolio_settings_repo

ZERO = Decimal(0)
MAX_TOTAL_PCT = Decimal(100)


class TargetWeightExceeded(Exception):
    def __init__(self, total: Decimal):
        self.total = total
        super().__init__(f"Target weights would total {total}% — reduce this or another holding's target first.")


def set_asset_target_weight(db: Session, portfolio_id: int, asset_id: int, value: Decimal | None) -> None:
    asset = asset_repo.get_asset(db, asset_id)
    if asset is None:
        raise ValueError("Asset not found")

    if value is not None:
        # Excludes this asset's *own* current value from the sum — otherwise raising an
        # existing target would double-count it against itself.
        others_total = portfolio_asset_target_repo.sum_targets(db, portfolio_id, exclude_asset_id=asset_id)
        cash = portfolio_settings_repo.get_cash_target_weight_pct(db, portfolio_id) or ZERO
        total = others_total + cash + value
        if total > MAX_TOTAL_PCT:
            raise TargetWeightExceeded(total)

    portfolio_asset_target_repo.set_target(db, portfolio_id, asset_id, value)


def set_cash_target_weight(db: Session, portfolio_id: int, value: Decimal | None) -> None:
    if value is not None:
        assets_total = portfolio_asset_target_repo.sum_targets(db, portfolio_id, exclude_asset_id=None)
        total = assets_total + value
        if total > MAX_TOTAL_PCT:
            raise TargetWeightExceeded(total)

    portfolio_settings_repo.set_cash_target_weight_pct(db, portfolio_id, value)
