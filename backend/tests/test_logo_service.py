from datetime import date, timedelta

import pytest

from app.models.asset import Asset
from app.services.logo_provider import (
    GOOD_ENOUGH_PX,
    LogoImage,
    LogoProvider,
    WebsiteLogoProvider,
    _declared_px,
    _domain,
    _is_fetchable,
    _largest_ico_frame,
    _pixel_size,
    DARK_BACKDROP,
    _composite_on_dark,
    _needs_dark_backdrop,
)
from app.services.logo_service import LogoService


class FakeProvider(LogoProvider):
    def __init__(self, image: LogoImage | None):
        self.image = image
        self.calls: list[str] = []

    def get_logo(self, symbol: str, name: str) -> LogoImage | None:
        self.calls.append(symbol)
        return self.image


PNG = LogoImage(content_type="image/png", data=b"\x89PNG-bytes", source_url="https://acme.com/apple-touch-icon.png")


def make_asset(db, **overrides) -> Asset:
    fields = {"ticker": "ACME", "name": "Acme Inc", "asset_class": "equity", "native_currency": "EUR",
              "yahoo_symbol": "ACME"}
    fields.update(overrides)
    asset = Asset(**fields)
    db.add(asset)
    db.flush()
    return asset


def test_fetched_logo_is_cached_and_the_provider_is_not_asked_again(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(PNG)
    service = LogoService(provider)

    first = service.get_logo(db_session, asset)
    second = service.get_logo(db_session, asset)

    assert first is not None and first.image == PNG.data and first.content_type == "image/png"
    assert second is not None and second.image == PNG.data
    assert provider.calls == ["ACME"]


def test_a_miss_is_retried_at_most_once_a_day(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(None)
    service = LogoService(provider)

    assert service.get_logo(db_session, asset) is None
    assert service.get_logo(db_session, asset) is None
    assert provider.calls == ["ACME"]

    # ...but a new day earns the asset one more attempt, in case the site has since added one
    asset.logo_checked_at = date.today() - timedelta(days=1)
    assert service.get_logo(db_session, asset) is None
    assert provider.calls == ["ACME", "ACME"]


def test_asset_with_no_price_symbol_is_never_looked_up(db_session):
    asset = make_asset(db_session, ticker="MYSTERY", yahoo_symbol=None)
    provider = FakeProvider(PNG)

    assert LogoService(provider).get_logo(db_session, asset) is None
    assert provider.calls == []


def test_a_provider_that_raises_costs_one_attempt_not_a_broken_page(db_session):
    class ExplodingProvider(LogoProvider):
        def get_logo(self, symbol: str, name: str) -> LogoImage | None:
            raise RuntimeError("provider down")

    asset = make_asset(db_session)
    with pytest.raises(RuntimeError):
        LogoService(ExplodingProvider()).get_logo(db_session, asset)

    # the attempt is stamped before the call, so a provider stuck in a failure loop can't be
    # re-hit once per rendered row
    assert asset.logo_checked_at == date.today()


@pytest.mark.parametrize(
    "website",
    ["http://localhost/", "https://192.168.1.10/", "ftp://acme.com/", "https://server.local/", "", None],
)
def test_non_public_websites_are_not_fetched(website):
    assert _domain(website) is None


@pytest.mark.parametrize(
    ("website", "expected"),
    [
        ("https://www.acme.com/investors", "www.acme.com"),
        ("http://acme.co.uk", "acme.co.uk"),
        ("acme.com", "acme.com"),  # yfinance sometimes returns a bare host
        ("https://ACME.com", "acme.com"),
    ],
)
def test_public_websites_resolve_to_their_host(website, expected):
    assert _domain(website) == expected


# -- brand resolution -------------------------------------------------------


def candidates(symbol: str, name: str, website: str | None = None) -> list[str]:
    """Domains the provider would try, with the slow yfinance lookup stubbed out."""

    class Provider(WebsiteLogoProvider):
        def _website(self, symbol: str) -> str | None:
            return website

    return list(Provider()._candidate_domains(symbol, name))


def test_a_fund_is_branded_by_its_issuer_read_out_of_its_own_name():
    # yfinance reports no website for these, so the fund's title is the only thing that says
    # whose logo belongs on the row.
    assert candidates("SMH.MI", "VanEck Semiconductor ETF")[0] == "vaneck.com"
    assert candidates("TDIV.AS", "VanEck Ms Developed Markets Div Lead UCITS ETF")[0] == "vaneck.com"
    assert candidates("GRID.MI", "First Trust Nasdaq Clean Edge Smart Grid UCITS ETF")[0] == "ftportfolios.com"


def test_alphabet_resolves_to_the_mark_people_recognise():
    # abc.xyz is where Alphabet files; Google is the logo anyone would identify in a table.
    assert candidates("GOOGL", "Alphabet Inc Class A", website="https://abc.xyz")[0] == "google.com"


def test_an_exchange_suffix_does_not_hide_a_symbol_override():
    assert candidates("GOOGL.MI", "Alphabet Inc")[0] == "google.com"


def test_the_issuers_own_website_is_still_the_fallback():
    assert candidates("ABN.AS", "ABN Amro Bank NV", website="https://www.abnamro.com") == ["www.abnamro.com"]


def test_a_matched_brand_still_falls_back_to_the_website_if_its_icon_is_missing():
    # Ordered, not exclusive: a bad guess costs one extra request, never the logo itself.
    assert candidates("SMH.MI", "VanEck Semiconductor ETF", website="https://vaneck.com/etf") == [
        "vaneck.com",
        "vaneck.com",
    ]


def test_only_the_most_specific_issuer_matches():
    # "Trust" appears in plenty of fund names; the longest key must win outright rather than
    # letting a shorter one queue a second, wrong domain.
    found = candidates("GRID.MI", "First Trust Global Vanguard-style Fund")
    assert found == ["ftportfolios.com"]


# -- picking a logo that isn't blurry ---------------------------------------
# A logo is drawn at 28-36 CSS px, so on a 2x display a 16px favicon.ico is upscaled 3-4x.
# These cover the measuring that lets the provider prefer the artwork a site actually has.


def png(width: int, height: int) -> bytes:
    import struct

    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height)


def ico(*frames: tuple[int, int]) -> bytes:
    """A minimal multi-frame .ico with one byte of payload per frame."""
    import struct

    header = b"\x00\x00\x01\x00" + struct.pack("<H", len(frames))
    offset = 6 + 16 * len(frames)
    entries, payloads = b"", b""
    for index, (width, height) in enumerate(frames):
        body = bytes([index]) * 32
        entries += bytes([width % 256, height % 256, 0, 0]) + struct.pack("<HHII", 1, 32, len(body), offset)
        offset += len(body)
        payloads += body
    return header + entries + payloads


def test_pixel_size_reads_each_format_from_its_header():
    assert _pixel_size(png(180, 180), "image/png") == 180
    assert _pixel_size(png(200, 120), "image/png") == 120  # the short side is what constrains it
    assert _pixel_size(ico((16, 16), (48, 48)), "image/x-icon") == 48  # best frame available
    assert _pixel_size(b"GIF89a" + (64).to_bytes(2, "little") + (64).to_bytes(2, "little"), "image/gif") == 64
    assert _pixel_size(b"not an image", "image/png") == 0


def test_a_square_vector_scores_ideal_but_a_wordmark_is_unusable():
    square = b'<svg viewBox="0 0 512 512"></svg>'
    wordmark = b'<svg viewBox="0 0 145 35"></svg>'  # VanEck's logo, a sliver in a square tile
    assert _pixel_size(square, "image/svg+xml") == GOOD_ENOUGH_PX
    assert _pixel_size(wordmark, "image/svg+xml") == 0


def test_a_multi_frame_icon_is_trimmed_to_its_largest_frame():
    # Browsers pick a frame out of a multi-frame .ico themselves, and at this display size
    # routinely pick the smallest one.
    trimmed = _largest_ico_frame(ico((16, 16), (48, 48), (32, 32)))

    import struct

    assert struct.unpack("<H", trimmed[4:6])[0] == 1
    assert _pixel_size(trimmed, "image/x-icon") == 48
    # the surviving frame's own bytes are copied across untouched
    assert trimmed[22:] == bytes([1]) * 32


def test_trimming_leaves_a_single_frame_icon_and_a_non_icon_alone():
    single = ico((32, 32))
    assert _largest_ico_frame(single) == single
    assert _largest_ico_frame(png(64, 64)) == png(64, 64)
    assert _largest_ico_frame(b"") == b""


def test_declared_sizes_are_read_as_the_largest_square_offered():
    assert _declared_px("16x16 32x32 192x192") == 192
    assert _declared_px("180X180") == 180
    assert _declared_px("any") == 0  # a vector, which carries no pixel size
    assert _declared_px(None) == 0


def test_only_real_web_addresses_are_requested():
    # Icon hrefs come out of someone else's markup and can be anything at all.
    assert _is_fetchable("https://cdn.example.com/icon-192.png")
    assert not _is_fetchable("data:image/png;base64,AAAA")
    assert not _is_fetchable("javascript:alert(1)")
    assert not _is_fetchable("/relative/icon.png")


# -- artwork that would be invisible ----------------------------------------


def image_bytes(colour: tuple[int, int, int, int], size: int = 32, fill_fraction: float = 0.3) -> bytes:
    """A square with `colour` painted over part of it, the rest fully transparent."""
    import io

    from PIL import Image

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    painted = int(size * fill_fraction)
    for x in range(painted):
        for y in range(size):
            image.putpixel((x, y), colour)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_white_artwork_on_transparency_is_recognised_as_needing_a_backdrop():
    # Brands routinely publish only the white variant of a mark, for use on a dark header.
    assert _needs_dark_backdrop(image_bytes((255, 255, 255, 255)))


def test_dark_artwork_on_transparency_is_left_alone():
    assert not _needs_dark_backdrop(image_bytes((20, 30, 60, 255)))


def test_an_opaque_image_is_left_alone_however_light_it_is():
    # A white favicon with a solid background is already visible; there's nothing to place.
    assert not _needs_dark_backdrop(image_bytes((255, 255, 255, 255), fill_fraction=1.0))


def test_an_undecodable_image_is_left_alone_rather_than_raising():
    assert not _needs_dark_backdrop(b"not an image at all")


def test_compositing_produces_an_opaque_image_on_the_dark_backdrop():
    import io

    from PIL import Image

    composited = _composite_on_dark(image_bytes((255, 255, 255, 255)))

    with Image.open(io.BytesIO(composited)) as result:
        assert result.mode == "RGB"  # no alpha left to render as blank
        # a transparent corner now carries the backdrop, and the artwork is still white
        assert result.getpixel((result.width - 1, 0)) == DARK_BACKDROP
        assert result.getpixel((0, 0)) == (255, 255, 255)
