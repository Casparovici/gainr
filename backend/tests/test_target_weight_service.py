from decimal import Decimal

import pytest

from app.models.asset import Asset
from app.repositories import portfolio_asset_target_repo
from app.services.target_weight_service import TargetWeightExceeded, set_asset_target_weight, set_cash_target_weight


def make_asset(db, ticker="ACME") -> Asset:
    asset = Asset(ticker=ticker, name=f"{ticker} Inc", asset_class="equity", native_currency="EUR")
    db.add(asset)
    db.flush()
    return asset


def test_setting_a_target_weight_within_headroom_succeeds(db_session, portfolio_id):
    asset = make_asset(db_session)
    db_session.commit()

    set_asset_target_weight(db_session, portfolio_id, asset.id, Decimal(30))
    db_session.commit()

    assert portfolio_asset_target_repo.get(db_session, portfolio_id, asset.id).target_weight_pct == Decimal(30)


def test_setting_a_target_weight_that_would_exceed_100_is_rejected(db_session, portfolio_id):
    a = make_asset(db_session, "A")
    b = make_asset(db_session, "B")
    db_session.commit()
    set_asset_target_weight(db_session, portfolio_id, a.id, Decimal(70))
    db_session.commit()

    with pytest.raises(TargetWeightExceeded) as exc_info:
        set_asset_target_weight(db_session, portfolio_id, b.id, Decimal(40))

    assert exc_info.value.total == Decimal(110)
    assert portfolio_asset_target_repo.get(db_session, portfolio_id, b.id) is None  # rejected write left no row


def test_updating_an_existing_weight_excludes_its_own_old_value_from_the_sum(db_session, portfolio_id):
    """The classic off-by-self bug: raising an asset's own target must not count its old
    value against itself."""
    a = make_asset(db_session, "A")
    b = make_asset(db_session, "B")
    db_session.commit()
    set_asset_target_weight(db_session, portfolio_id, a.id, Decimal(50))
    set_asset_target_weight(db_session, portfolio_id, b.id, Decimal(30))
    db_session.commit()

    # Raising A from 50 to 70 makes the total 70 + 30 = 100 -- must succeed, not be rejected
    # as if A's old 50 were still counted alongside the new 70.
    set_asset_target_weight(db_session, portfolio_id, a.id, Decimal(70))
    db_session.commit()

    assert portfolio_asset_target_repo.get(db_session, portfolio_id, a.id).target_weight_pct == Decimal(70)


def test_cash_target_weight_counts_toward_the_same_cap(db_session, portfolio_id):
    asset = make_asset(db_session)
    db_session.commit()
    set_asset_target_weight(db_session, portfolio_id, asset.id, Decimal(80))
    db_session.commit()

    with pytest.raises(TargetWeightExceeded):
        set_cash_target_weight(db_session, portfolio_id, Decimal(25))

    set_cash_target_weight(db_session, portfolio_id, Decimal(20))  # exactly 100 total is fine
    db_session.commit()


def test_clearing_a_target_weight_never_needs_the_headroom_check(db_session, portfolio_id):
    a = make_asset(db_session, "A")
    b = make_asset(db_session, "B")
    db_session.commit()
    set_asset_target_weight(db_session, portfolio_id, a.id, Decimal(90))
    set_asset_target_weight(db_session, portfolio_id, b.id, Decimal(10))
    db_session.commit()

    set_asset_target_weight(db_session, portfolio_id, a.id, None)
    db_session.commit()

    assert portfolio_asset_target_repo.get(db_session, portfolio_id, a.id) is None


def test_unknown_asset_raises(db_session, portfolio_id):
    with pytest.raises(ValueError):
        set_asset_target_weight(db_session, portfolio_id, 9999, Decimal(10))


def test_target_weight_headroom_is_checked_per_portfolio(db_session, portfolio_id):
    from app.models.portfolio import Portfolio

    other = Portfolio(name="Other Portfolio")
    db_session.add(other)
    asset = make_asset(db_session)
    db_session.commit()
    set_asset_target_weight(db_session, portfolio_id, asset.id, Decimal(90))
    db_session.commit()

    # Another portfolio's 90% headroom is untouched by this one's -- must not raise.
    set_asset_target_weight(db_session, other.id, asset.id, Decimal(90))
    db_session.commit()

    assert portfolio_asset_target_repo.get(db_session, portfolio_id, asset.id).target_weight_pct == Decimal(90)
    assert portfolio_asset_target_repo.get(db_session, other.id, asset.id).target_weight_pct == Decimal(90)
