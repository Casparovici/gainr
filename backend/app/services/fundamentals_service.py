"""Serves company news and financial statements for a position card, caching the slow
external lookups behind a TTL.

Both are scrapes measured in seconds, and a card can be opened and closed repeatedly, so
nothing is fetched twice inside its window. The TTLs differ because the data does: headlines
turn over through the day, statements only at results.
"""

import json
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.repositories import snapshot_repo
from app.schemas.fundamentals import (
    FinancialPeriodOut,
    FinancialsOut,
    KeyMetricsOut,
    NewsItemOut,
    NewsOut,
    NewsSourceOut,
    PositionMetricOut,
    PositionMetricsOut,
)
from app.services import fundamentals_metrics, news_sources
from app.services.fundamentals_provider import FundamentalsProvider, NewsItem, YFinanceFundamentalsProvider

NEWS_KIND = "news"
FINANCIALS_KIND = "financials"
METRICS_KIND = "metrics"

NEWS_TTL = timedelta(hours=3)
# Bumped when the provider's news feed changes, so a cache filled from the old one -- empty,
# when Yahoo retired the endpoint yfinance used -- is refetched rather than served for its TTL.
NEWS_FEED = 2
FINANCIALS_TTL = timedelta(days=1)
METRICS_TTL = timedelta(days=1)

# The card promises "the past week" and says so on screen.
NEWS_WINDOW_DAYS = 7
# With extra sources a position can pull in dozens of stories; the card is a skim, not an archive.
MAX_MERGED_NEWS = 30


class FundamentalsService:
    def __init__(self, provider: FundamentalsProvider | None = None):
        self.provider = provider or YFinanceFundamentalsProvider()

    def get_news(self, db: Session, asset: Asset) -> NewsOut:
        sources = news_sources.parse_stored(asset.news_sources)
        cached = self._cached(db, asset, NEWS_KIND, NEWS_TTL)
        # The cache remembers which sources it was built from: after the user adds or removes
        # one, the old payload is stale even inside its TTL. (A bare list is the format from
        # before sources existed -- stale too, as is anything from an older NEWS_FEED.)
        if not (isinstance(cached, dict) and cached.get("sources") == sources and cached.get("feed") == NEWS_FEED):
            items = self._merged_news(asset, sources)
            cached = {"feed": NEWS_FEED, "sources": sources, "items": [i.model_dump(mode="json") for i in items]}
            self._store(db, asset, NEWS_KIND, cached)

        # Filtered on the way out, not on the way in: the cache outlives a few hours, and the
        # week it's measured against moves in the meantime.
        cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_WINDOW_DAYS)
        recent = [
            item for item in (NewsItemOut(**raw) for raw in cached["items"])
            if item.published_at.astimezone(timezone.utc) >= cutoff
        ]
        return NewsOut(
            window_days=NEWS_WINDOW_DAYS,
            items=recent,
            sources=[NewsSourceOut(key=src, label=news_sources.label(src)) for src in sources],
        )

    def _merged_news(self, asset: Asset, sources: list[str]) -> list[NewsItemOut]:
        """The position's own news plus each extra source's, newest first. A story that shows up
        in several feeds (a defence stock's news in both its own and its industry's feed) is
        kept once, attributed to the position itself when it's there."""
        feeds: list[tuple[str | None, list[NewsItem]]] = [
            (None, self.provider.get_news(asset.yahoo_symbol) if asset.yahoo_symbol else []),
        ]
        feeds += [(news_sources.label(src), self.provider.get_source_news(src)) for src in sources]

        seen: set[str] = set()
        merged: list[NewsItemOut] = []
        for source_label, items in feeds:
            for i in items:
                keys = {i.url, i.title.strip().lower()}
                # Only a source's stories are checked against what's already in: the position's
                # own feed is taken as-is, exactly as it was before sources existed.
                if source_label is not None and keys & seen:
                    continue
                seen |= keys
                merged.append(
                    NewsItemOut(
                        title=i.title, summary=i.summary, publisher=i.publisher,
                        url=i.url, published_at=i.published_at, source=source_label,
                    )
                )
        merged.sort(key=lambda i: i.published_at, reverse=True)
        return merged[:MAX_MERGED_NEWS]

    def set_news_sources(self, db: Session, asset: Asset, sources: list[str]) -> list[str]:
        """Validates and stores the position's extra sources (InvalidNewsSource if one is
        unknown). The cached news notices the change on its next read -- see get_news."""
        cleaned = news_sources.validate(sources)
        asset.news_sources = json.dumps(cleaned) if cleaned else None
        db.flush()
        return cleaned

    def get_financials(self, db: Session, asset: Asset) -> FinancialsOut:
        cached = self._cached(db, asset, FINANCIALS_KIND, FINANCIALS_TTL)
        if cached is not None:
            try:
                return FinancialsOut(**cached)
            except ValidationError:
                # A cache row written before a field was added or renamed reads the same as a
                # corrupt one -- re-fetch rather than 500 for the rest of the day's TTL.
                pass

        financials = self.provider.get_financials(asset.yahoo_symbol) if asset.yahoo_symbol else None
        out = FinancialsOut(
            currency=financials.currency if financials else None,
            quarter=FinancialPeriodOut.model_validate(financials.quarter) if financials and financials.quarter else None,
            annual=[FinancialPeriodOut.model_validate(p) for p in financials.annual] if financials else [],
            key_metrics=(
                KeyMetricsOut.model_validate(financials.key_metrics) if financials and financials.key_metrics else None
            ),
        )
        self._store(db, asset, FINANCIALS_KIND, out.model_dump(mode="json"))
        return out

    def get_metrics(self, db: Session, asset: Asset) -> PositionMetricsOut:
        """The position's analyst checklist (see fundamentals_metrics). A position without one
        answers empty and fetches nothing."""
        profile = fundamentals_metrics.profile_for(asset.yahoo_symbol)
        if profile is None:
            return PositionMetricsOut(lens=None, currency=None, metrics=[])
        cached = self._cached(db, asset, METRICS_KIND, METRICS_TTL)
        if cached is not None:
            try:
                return PositionMetricsOut(**cached)
            except ValidationError:
                pass
        inputs = self.provider.get_metric_inputs(asset.yahoo_symbol, profile.kind, profile.price_symbols)
        built = fundamentals_metrics.build_metrics(profile, inputs)
        out = PositionMetricsOut(
            lens=built.lens,
            currency=built.currency,
            metrics=[PositionMetricOut.model_validate(m) for m in built.metrics],
        )
        self._store(db, asset, METRICS_KIND, out.model_dump(mode="json"))
        return out

    @staticmethod
    def _cached(db: Session, asset: Asset, kind: str, ttl: timedelta):
        snapshot = snapshot_repo.get_fresh(db, asset.id, kind, ttl)
        if snapshot is None:
            return None
        try:
            return json.loads(snapshot.payload)
        except json.JSONDecodeError:
            # A payload we can't read is worth exactly as much as no payload — re-fetch.
            return None

    @staticmethod
    def _store(db: Session, asset: Asset, kind: str, payload) -> None:
        snapshot_repo.upsert(db, asset.id, kind, json.dumps(payload))


fundamentals_service = FundamentalsService()
