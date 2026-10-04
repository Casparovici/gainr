"""Covers the gripr bank-logo catalog: the fixed key list, fetch-and-cache-once behavior, and
the account picker's key validation. Mirrors test_assets_router.py's caching-contract coverage
for the logo endpoint itself.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_bank_logo import GriprBankLogo
from app.routers import gripr as gripr_router
from app.services.logo_provider import LogoImage
from app.services.gripr_bank_logo_service import GRIPR_BANKS, GriprBankLogoService

PNG = b"\x89PNG\r\n\x1a\n-pretend-bank-logo-bytes"


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_account(db, name="Spaarrekening") -> GriprAccount:
    account = GriprAccount(name=name, type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db.add(account)
    db.flush()
    return account


# -- catalog --------------------------------------------------------------------------------


def test_lists_the_fixed_catalog(client):
    response = client.get("/api/gripr/bank-logos")

    assert response.status_code == 200
    keys = {row["key"] for row in response.json()}
    assert keys == set(GRIPR_BANKS.keys())


# -- logo endpoint ----------------------------------------------------------------------------


def test_a_cached_logo_is_served_with_a_validator(client, db_session):
    db_session.add(GriprBankLogo(key="ing", content_type="image/png", image=PNG, source_url="https://ing.nl/icon.png"))
    db_session.commit()

    response = client.get("/api/gripr/bank-logos/ing/logo")

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["etag"]
    assert "no-cache" in response.headers["cache-control"]


def test_an_unchanged_logo_costs_a_304(client, db_session):
    db_session.add(GriprBankLogo(key="ing", content_type="image/png", image=PNG, source_url="https://ing.nl/icon.png"))
    db_session.commit()
    etag = client.get("/api/gripr/bank-logos/ing/logo").headers["etag"]

    response = client.get("/api/gripr/bank-logos/ing/logo", headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.content == b""


def test_an_unknown_key_is_a_plain_404(client):
    response = client.get("/api/gripr/bank-logos/does-not-exist/logo")

    assert response.status_code == 404


# -- fetch-and-cache-once --------------------------------------------------------------------


class FakeProvider:
    def __init__(self, image):
        self.image = image
        self.calls: list[str] = []

    def get_logo_for_domain(self, domain: str):
        self.calls.append(domain)
        return self.image


def test_an_uncached_key_is_fetched_once_and_then_served_from_cache(db_session):
    provider = FakeProvider(LogoImage(content_type="image/png", data=PNG, source_url="https://ing.nl/icon.png"))
    service = GriprBankLogoService(provider)

    first = service.get_logo(db_session, "ing")
    db_session.commit()
    second = service.get_logo(db_session, "ing")

    assert first is not None and first.image == PNG
    assert second is not None and second.image == PNG
    assert provider.calls == ["ing.nl"]  # only fetched once -- the second call hit the cache


def test_a_provider_miss_is_a_plain_none_not_an_error(db_session):
    # "ing" has no local override, so a provider miss for it is a genuine miss.
    service = GriprBankLogoService(FakeProvider(None))

    assert service.get_logo(db_session, "ing") is None


def test_an_unknown_key_is_never_looked_up(db_session):
    provider = FakeProvider(LogoImage(content_type="image/png", data=PNG, source_url="https://x"))

    assert GriprBankLogoService(provider).get_logo(db_session, "not-a-real-bank") is None
    assert provider.calls == []


# -- local overrides (traderepublic, revolut) ----------------------------------------------


def test_traderepublic_and_revolut_resolve_from_a_local_file_not_the_network(db_session):
    # A provider that would error if ever called -- proves the local override short-circuits
    # the network path entirely for these two keys.
    class ExplodingProvider:
        def get_logo_for_domain(self, domain: str):
            raise AssertionError(f"should not have looked up {domain} over the network")

    service = GriprBankLogoService(ExplodingProvider())

    for key in ("traderepublic", "revolut"):
        logo = service.get_logo(db_session, key)
        assert logo is not None
        assert logo.content_type == "image/png"
        assert logo.source_url.startswith("local:")
        assert len(logo.image) > 0


def test_a_local_override_logo_is_served_over_http_too(client, db_session):
    response = client.get("/api/gripr/bank-logos/traderepublic/logo")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


# -- account picker validation ------------------------------------------------------------------


def test_setting_a_known_bank_logo_key_on_an_account(client, db_session):
    account = make_account(db_session)
    db_session.commit()

    response = client.put(f"/api/gripr/accounts/{account.id}", json={"bank_logo_key": "trading212"})

    assert response.status_code == 200
    assert response.json()["bank_logo_key"] == "trading212"


def test_an_unknown_bank_logo_key_is_rejected(client, db_session):
    account = make_account(db_session)
    db_session.commit()

    response = client.put(f"/api/gripr/accounts/{account.id}", json={"bank_logo_key": "some-random-bank"})

    assert response.status_code == 400


def test_clearing_a_bank_logo_key_back_to_none(client, db_session):
    account = make_account(db_session)
    db_session.commit()
    client.put(f"/api/gripr/accounts/{account.id}", json={"bank_logo_key": "revolut"})

    response = client.put(f"/api/gripr/accounts/{account.id}", json={"bank_logo_key": None})

    assert response.status_code == 200
    assert response.json()["bank_logo_key"] is None
