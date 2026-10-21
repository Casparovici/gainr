"""WebsiteLogoProvider's fetching, against httpx's MockTransport: which icon a site's own
markup and manifest lead to, and which answers are refused. No network."""

import io
import json

import httpx
import pytest
from PIL import Image

from app.services import logo_provider
from app.services.logo_provider import WebsiteLogoProvider


def png(size: int, color=(200, 30, 30, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (size, size), color).save(buf, format="PNG")
    return buf.getvalue()


def image(data: bytes, content_type="image/png") -> httpx.Response:
    return httpx.Response(200, content=data, headers={"content-type": content_type})


def page(html: str) -> httpx.Response:
    return httpx.Response(200, text=html, headers={"content-type": "text/html"})


class StubbedProvider(WebsiteLogoProvider):
    """The real provider with the network swapped for `routes` (full URL -> response) and the
    yfinance website lookup for a fixed answer."""

    def __init__(self, routes: dict[str, httpx.Response], website: str | None = None):
        self.routes, self.website, self.requested = routes, website, []

    def _website(self, symbol: str) -> str | None:
        return self.website

    def _client(self) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            self.requested.append(url)
            return self.routes.get(url, httpx.Response(404))

        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_the_largest_icon_the_page_and_its_manifest_declare_wins():
    provider = StubbedProvider(
        {
            "https://acme.com/": page(
                '<link rel="icon" href="/small.png" sizes="32x32">'
                '<link rel="apple-touch-icon" href="//cdn.acme.com/touch.png" sizes="180x180">'
                '<link rel="manifest" href="/site.webmanifest">'
            ),
            "https://acme.com/site.webmanifest": httpx.Response(
                200, text=json.dumps({"icons": [{"src": "/icon-512.png", "sizes": "512x512"}]})
            ),
            "https://acme.com/icon-512.png": image(png(512)),
            "https://cdn.acme.com/touch.png": image(png(180)),
            "https://acme.com/small.png": image(png(32)),
        },
        website="https://acme.com/about",
    )

    logo = provider.get_logo("ACME", "Acme Corp")

    assert logo.source_url == "https://acme.com/icon-512.png"
    assert logo.content_type == "image/png"
    # 512px is good enough, so nothing smaller is fetched after it.
    assert "https://acme.com/small.png" not in provider.requested


def test_without_declared_icons_the_conventional_paths_are_tried():
    provider = StubbedProvider(
        {
            "https://acme.com/": page("<html>no icons here</html>"),
            # An HTML shell answered with 200 instead of a 404 is not an icon.
            "https://acme.com/apple-touch-icon.png": page("<html>not found</html>"),
            "https://acme.com/favicon.png": image(png(64)),
        },
        website="https://acme.com",
    )
    assert provider.get_logo("ACME", "Acme").source_url == "https://acme.com/favicon.png"


def test_an_oversized_or_empty_image_is_refused():
    provider = StubbedProvider(
        {
            "https://acme.com/": page('<link rel="icon" href="/huge.png"><link rel="icon" href="/empty.png">'),
            "https://acme.com/huge.png": image(b"\x89PNG" + b"0" * (logo_provider.MAX_LOGO_BYTES + 1)),
            "https://acme.com/empty.png": image(b""),
        },
        website="https://acme.com",
    )
    assert provider.get_logo("ACME", "Acme") is None


def test_a_hand_picked_icon_url_comes_first():
    override = logo_provider.ICON_URL_OVERRIDES["vaneck"]
    provider = StubbedProvider({override: image(png(256))})
    logo = provider.get_logo("SMH", "VanEck Semiconductor ETF")
    assert logo.source_url == override
    assert provider.requested == [override]


def test_a_known_domain_is_asked_directly():
    provider = StubbedProvider({"https://ing.nl/": page(""), "https://ing.nl/apple-touch-icon.png": image(png(180))})
    assert provider.get_logo_for_domain("ing.nl").source_url == "https://ing.nl/apple-touch-icon.png"


def test_a_broken_manifest_and_a_failing_homepage_are_shrugged_off():
    provider = StubbedProvider(
        {
            "https://acme.com/": page('<link rel="manifest" href="/m.json">'),
            "https://acme.com/m.json": httpx.Response(200, text="{not json"),
            "https://acme.com/favicon.svg": image(b'<svg viewBox="0 0 64 64"></svg>', "image/svg+xml"),
        },
        website="https://acme.com",
    )
    assert provider.get_logo("ACME", "Acme").content_type == "image/svg+xml"
    assert StubbedProvider({"https://acme.com/": httpx.Response(500)}).get_logo_for_domain("acme.com") is None


def test_an_icon_pointing_at_a_private_address_is_never_requested():
    provider = StubbedProvider(
        {"https://acme.com/": page('<link rel="icon" href="http://192.168.1.1/router.png" sizes="512x512">')},
        website="https://acme.com",
    )
    provider.get_logo("ACME", "Acme")
    assert not any("192.168" in url for url in provider.requested)


def test_white_artwork_is_put_on_a_dark_backdrop():
    white = png(128, (255, 255, 255, 255))
    buf = io.BytesIO()
    canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    canvas.paste(Image.open(io.BytesIO(white)).crop((32, 32, 96, 96)), (32, 32))
    canvas.save(buf, format="PNG")
    provider = StubbedProvider({"https://acme.com/": page('<link rel="icon" href="/w.png">'), "https://acme.com/w.png": image(buf.getvalue())})

    logo = provider.get_logo_for_domain("acme.com")

    corner = Image.open(io.BytesIO(logo.data)).convert("RGBA").getpixel((0, 0))
    assert corner[:3] == logo_provider.DARK_BACKDROP


@pytest.mark.parametrize("raises", [httpx.ConnectError("down"), RuntimeError("bug")])
def test_a_client_that_fails_outright_is_no_logo(raises):
    class Failing(StubbedProvider):
        def _client(self):
            raise raises

    assert Failing({}).get_logo("ACME", "Acme") is None
    assert Failing({}).get_logo_for_domain("acme.com") is None
