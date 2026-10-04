"""Reference indices the portfolio can be compared against on the performance chart.

Each benchmark is stored as a synthetic pseudo-asset (ticker `BM:<key>`, asset_class
"benchmark") so it inherits the whole price pipeline for free: `price_history` caching,
the once-per-day refresh, and historical backfill.

Benchmarks are compared as *index performance in their own currency* — that's the number
you'd see quoted for the index anywhere else, so it stays verifiable. It deliberately does
not fold in EUR/USD moves, so it isn't the return a euro investor would have realised.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.repositories import asset_repo, price_repo
from app.services.price_service import price_service


@dataclass(frozen=True)
class BenchmarkDef:
    key: str
    label: str
    symbol: str


BENCHMARKS: dict[str, BenchmarkDef] = {
    "sp500": BenchmarkDef("sp500", "S&P 500", "^GSPC"),
    "nasdaq": BenchmarkDef("nasdaq", "Nasdaq Composite", "^IXIC"),
    "iwda": BenchmarkDef("iwda", "iShares MSCI World (IWDA)", "IWDA.AS"),
}


class BenchmarkService:
    def list_benchmarks(self) -> list[BenchmarkDef]:
        return list(BENCHMARKS.values())

    def _asset(self, db: Session, benchmark: BenchmarkDef) -> Asset:
        return asset_repo.get_or_create_asset(
            db,
            ticker=f"BM:{benchmark.key}",
            name=benchmark.label,
            asset_class="benchmark",
            native_currency="EUR",  # refined by sync_currency on first price fetch
            yahoo_symbol=benchmark.symbol,
        )

    def get_series(self, db: Session, key: str, start: date, end: date) -> list[tuple[date, Decimal]]:
        """Daily closes for one benchmark over [start, end], backfilling what's missing."""
        benchmark = BENCHMARKS.get(key)
        if benchmark is None:
            return []

        asset = self._asset(db, benchmark)
        price_service.ensure_history(db, asset, start, end)
        # Keeps today's point current without a second network round-trip on later loads.
        price_service.get_daily_price(db, asset)

        return [(row.date, Decimal(str(row.close_price))) for row in price_repo.get_history(db, asset.id, start, end)]


benchmark_service = BenchmarkService()
