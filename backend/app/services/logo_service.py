"""Resolves and caches a brand logo per asset.

Same shape as PriceService: the expensive external lookup happens at most once per asset per
calendar day (tracked on `Asset.logo_checked_at`), and everything after that is served from
the local `asset_logos` cache with no network calls at all. Unlike prices there's nothing to
refresh — once an asset has a logo the cached bytes are simply reused forever.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.asset_logo import AssetLogo
from app.repositories import logo_repo
from app.services.logo_provider import LogoProvider, WebsiteLogoProvider


class LogoService:
    def __init__(self, provider: LogoProvider | None = None):
        self.provider = provider or WebsiteLogoProvider()

    def get_logo(self, db: Session, asset: Asset) -> AssetLogo | None:
        cached = logo_repo.get_logo(db, asset.id)
        if cached is not None:
            return cached
        if not asset.yahoo_symbol or asset.logo_checked_at == date.today():
            return None

        # Stamped before the fetch, so a provider that hangs or throws still costs one attempt
        # a day rather than one per page load.
        asset.logo_checked_at = date.today()
        db.flush()

        image = self.provider.get_logo(asset.yahoo_symbol, asset.name)
        if image is None:
            return None
        return logo_repo.upsert_logo(db, asset.id, image.content_type, image.data, image.source_url)


logo_service = LogoService()
