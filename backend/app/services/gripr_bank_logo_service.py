"""A small, fixed catalog of banks/brokers the user actually holds accounts with, each with a
locally-cached logo -- not a general lookup-any-brand system like gainr's asset logos
(see app/services/logo_service.py), since a gripr account isn't a ticker with a symbol to
resolve a brand from. Picking a key here just means "fetch (and remember) this exact domain's
icon." See docs/adr/0010.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.gripr_bank_logo import GriprBankLogo
from app.repositories import gripr_bank_logo_repo
from app.services.logo_provider import WebsiteLogoProvider

GRIPR_BANKS: dict[str, dict[str, str]] = {
    "ing": {"label": "ING", "domain": "ing.nl"},
    "trading212": {"label": "Trading 212", "domain": "trading212.com"},
    "traderepublic": {"label": "Trade Republic", "domain": "traderepublic.com"},
    "revolut": {"label": "Revolut", "domain": "revolut.com"},
}

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "gripr_bank_logos"

# A provided image, checked before ever hitting the network -- for a bank whose own site
# doesn't yield a usable icon through WebsiteLogoProvider (Trade Republic's only discoverable
# icon exceeds the size cap; Revolut's site 403s a plain request), the same way
# logo_provider.ICON_URL_OVERRIDES lets a specific asset stand in for gainr's assets. These two
# were supplied directly rather than found at a URL, so they're a local file, not a fetch.
LOCAL_OVERRIDES: dict[str, str] = {
    "traderepublic": "traderepublic.png",
    "revolut": "revolut.png",
}


class GriprBankLogoService:
    def __init__(self, provider: WebsiteLogoProvider | None = None):
        self.provider = provider or WebsiteLogoProvider()

    def get_logo(self, db: Session, key: str) -> GriprBankLogo | None:
        bank = GRIPR_BANKS.get(key)
        if bank is None:
            return None
        cached = gripr_bank_logo_repo.get_logo(db, key)
        if cached is not None:
            return cached

        override = LOCAL_OVERRIDES.get(key)
        if override is not None:
            data = (STATIC_DIR / override).read_bytes()
            return gripr_bank_logo_repo.upsert_logo(db, key, "image/png", data, f"local:{override}")

        image = self.provider.get_logo_for_domain(bank["domain"])
        if image is None:
            return None
        return gripr_bank_logo_repo.upsert_logo(db, key, image.content_type, image.data, image.source_url)


gripr_bank_logo_service = GriprBankLogoService()
