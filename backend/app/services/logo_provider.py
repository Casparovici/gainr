"""Strategy interface for resolving an asset's brand logo, so the backend isn't locked to
one source (the issuer's own website today; a paid logo API later).

Deliberately *not* backed by a third-party logo CDN: those work by taking a domain in the
URL, which would mean broadcasting every ticker in the portfolio to an outside host. The
issuer's own site is the one party that already knows you looked at it.
"""

import io
import ipaddress
import json
import re
import struct
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

# Comfortably above a real apple-touch-icon (usually < 50 KB) and far below anything that
# would be worth putting in a SQLite row.
MAX_LOGO_BYTES = 256 * 1024
FETCH_TIMEOUT_SECONDS = 6.0
# Conventional locations, tried only when a site declares nothing. apple-touch-icon comes
# first because it's a purpose-made square PNG; favicon.ico is last because it's usually a
# 16px container, which is exactly the thing that looks blurry in the UI.
ICON_PATHS = (
    "/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png",
    "/android-chrome-192x192.png",
    "/favicon.png",
    "/favicon.svg",
    "/favicon.ico",
)
# Sent when fetching a site's own pages and assets. A bare client gets a challenge page from
# plenty of CDNs; this is a plain browser string, not an attempt to look like a person.
USER_AGENT = "Mozilla/5.0 (compatible; gainr/1.0; local portfolio dashboard)"

# A logo is drawn at 28-36 CSS px, so on a 2x display anything under ~48px of real image is
# visibly soft — which is what made the favicon.ico fallbacks look blurry.
MIN_USEFUL_PX = 48
# Past this there's nothing to gain from fetching further candidates.
GOOD_ENOUGH_PX = 128
# A whole page load plus a handful of images, once per asset per day.
MAX_CANDIDATE_FETCHES = 6
# A wordmark ("VanEck" set in type, 145x35) shrunk into a square tile becomes an unreadable
# sliver, so anything this far from square is treated as unusable however large it is.
MAX_ASPECT_RATIO = 2.5

# Artwork drawn in white for use on a dark header is invisible on the light tile a logo sits
# on here. Above this mean luminance (0-255, measured over visible pixels only) a transparent
# image is treated as light-on-transparent and given a backdrop instead of being shown as a
# blank square.
LIGHT_INK_LUMINANCE = 170
# Pixels this faint are background, not ink, and shouldn't drag the average down.
ALPHA_VISIBLE_THRESHOLD = 32
# Neutral and dark enough for white artwork, and close to the slate the UI is built from.
DARK_BACKDROP = (15, 23, 42)


@dataclass
class LogoImage:
    content_type: str
    data: bytes
    source_url: str


@dataclass
class _Candidate:
    url: str
    # Size the site claims in its `sizes` attribute or manifest, used only for ordering —
    # what's actually fetched is measured, because plenty of sites declare sizes they don't
    # deliver.
    declared_px: int = 0


# Holdings whose recognisable brand doesn't live at the domain the issuer files under.
# Alphabet is the case in point: it publishes at abc.xyz, whose icon is a 16px monogram
# nobody would recognise in a table — the mark people know is Google's.
SYMBOL_DOMAINS = {
    "GOOGL": "google.com",
    "GOOG": "google.com",
    # Nu Holdings files as "Nu"; the bank everyone knows it as is Nubank, and nothing on the
    # holding company's name points there.
    "NU": "nubank.com.br",
}

# Artwork to use directly, for brands whose good mark isn't reachable from anything they
# declare. VanEck is the case that forced this: its site declares no icons at all, so
# discovery falls back to a 16px favicon, while the monogram below is a clean high-resolution
# square sitting in plain sight in the page's own markup. A deep asset URL can rot — if it
# does, resolution simply carries on down the chain to the domain candidates.
ICON_URL_OVERRIDES = {
    "vaneck": "https://www.vaneck.com/static/images/logo/VE_Logo_Monogram_wht_rgb.png",
}

# A fund is branded by whoever issues it, and yfinance reports no website at all for most
# ETFs — so the issuer is read out of the fund's own name instead ("VanEck Semiconductor
# ETF" -> vaneck.com). Every domain here was checked to actually serve an icon; matched
# longest-first so a more specific issuer can't be shadowed by a shorter one.
ISSUER_DOMAINS = {
    "first trust": "ftportfolios.com",
    "wisdomtree": "wisdomtree.com",
    "vanguard": "vanguard.com",
    "ishares": "ishares.com",
    "global x": "globalxetfs.com",
    "invesco": "invesco.com",
    "vaneck": "vaneck.com",
    "spdr": "ssga.com",
}


def _is_private_host(host: str) -> bool:
    """Whether `host` is loopback, link-local, or otherwise not a public internet address.

    Shared by `_domain` (the issuer domain itself) and `_is_fetchable` (icon URLs a fetched
    page points at, including its own manifest) — a page this app already decided to trust
    can still declare an icon at an internal address, and that shouldn't turn an asset-logo
    lookup into a request against the local network.
    """
    if not host or host == "localhost" or host.endswith(".local"):
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False  # an ordinary public hostname, not an IP literal
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved


def _is_fetchable(url: str) -> bool:
    """An ordinary http(s) URL with a public host.

    Icon hrefs are lifted out of someone else's markup, so they can be anything at all — a
    `data:` blob, a `javascript:` string, a mailto, or (if that site is malicious or
    compromised) a link into the local network this app runs on. Only real, public web
    addresses get requested.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    return not _is_private_host((parsed.hostname or "").lower())


def _largest_ico_frame(data: bytes) -> bytes:
    """An .ico carrying only its biggest frame, or the original if there's nothing to trim.

    A multi-frame .ico leaves the choice of frame to the renderer, and at the size a logo is
    drawn here browsers routinely pick the 16px one — which is how Google's mark ended up
    looking like a white smudge next to a 48px frame that was sitting in the same file.
    Rebuilding the container with a single frame settles it. Only the directory is rewritten;
    the frame's own bytes are copied across untouched.
    """
    if data[:4] != b"\x00\x00\x01\x00" or len(data) < 6:
        return data
    count = struct.unpack("<H", data[4:6])[0]
    if count <= 1:
        return data

    best_entry, best_px = None, -1
    for index in range(count):
        start = 6 + index * 16
        if start + 16 > len(data):
            break
        entry = data[start : start + 16]
        pixels = min(entry[0] or 256, entry[1] or 256)
        size, offset = struct.unpack("<II", entry[8:16])
        if pixels > best_px and offset + size <= len(data):
            best_entry, best_px = entry, pixels

    if best_entry is None:
        return data

    size, offset = struct.unpack("<II", best_entry[8:16])
    payload = data[offset : offset + size]
    # A single entry always sits immediately after the 6-byte header and its own 16-byte row.
    header = b"\x00\x00\x01\x00" + struct.pack("<H", 1)
    return header + best_entry[:8] + struct.pack("<II", size, 22) + payload


def _pixel_size(data: bytes, content_type: str) -> int:
    """Smallest side of the image, in real pixels — 0 when it can't be determined.

    The point is to tell a crisp 180px app icon from a 16px favicon without pulling in an
    imaging library for what is, in every format here, a header read. A vector image has no
    pixel size, so it scores as ideal unless its shape says wordmark.
    """
    if "svg" in content_type:
        return 0 if _is_wordmark_svg(data) else GOOD_ENOUGH_PX

    # PNG: IHDR is always the first chunk, width and height at a fixed offset.
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return min(width, height)

    # ICO: a directory of frames, each one byte per axis, where 0 means 256.
    if data[:4] == b"\x00\x00\x01\x00" and len(data) >= 6:
        count = struct.unpack("<H", data[4:6])[0]
        best = 0
        for index in range(count):
            entry = 6 + index * 16
            if entry + 16 > len(data):
                break
            best = max(best, min(data[entry] or 256, data[entry + 1] or 256))
        return best

    if data[:2] == b"\xff\xd8":
        return _jpeg_size(data)

    # GIF87a/GIF89a carry a little-endian logical screen size.
    if data[:3] == b"GIF" and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return min(width, height)

    return 0


def _jpeg_size(data: bytes) -> int:
    """Walks JPEG segments to the start-of-frame marker, which carries the dimensions."""
    offset = 2
    while offset + 9 < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        # SOF0-SOF15, excluding the four that aren't frame headers.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[offset + 5 : offset + 9])
            return min(width, height)
        if offset + 4 > len(data):
            break
        offset += 2 + struct.unpack(">H", data[offset + 2 : offset + 4])[0]
    return 0


def _is_wordmark_svg(data: bytes) -> bool:
    """Whether an SVG is a long logotype rather than a square mark."""
    head = data[:2000].decode("utf-8", "ignore")
    box = re.search(r'viewBox=["\']\s*[-\d.]+[,\s]+[-\d.]+[,\s]+([\d.]+)[,\s]+([\d.]+)', head)
    if not box:
        return False
    try:
        width, height = float(box.group(1)), float(box.group(2))
    except ValueError:
        return False
    if width <= 0 or height <= 0:
        return False
    return max(width / height, height / width) > MAX_ASPECT_RATIO


def _declared_px(sizes: str | None) -> int:
    """Largest square out of a `sizes` attribute like "16x16 32x32", or 0 for "any"."""
    if not sizes:
        return 0
    best = 0
    for token in re.findall(r"(\d+)\s*[xX]\s*(\d+)", sizes):
        best = max(best, min(int(token[0]), int(token[1])))
    return best


def _needs_dark_backdrop(data: bytes) -> bool:
    """Whether an image is light artwork on transparency, and so invisible on a light tile.

    Brands routinely publish only the white variant of a mark, meant for a dark header. Left
    alone it renders as an empty square, which reads as a bug rather than as a missing logo.
    """
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as image:
            image = image.convert("RGBA")
            pixels = list(image.get_flattened_data())
    except Exception:
        return False

    visible = [p for p in pixels if p[3] >= ALPHA_VISIBLE_THRESHOLD]
    if not visible or len(visible) > 0.9 * len(pixels):
        # Nothing visible, or effectively opaque — in either case there's no transparency to
        # place on a backdrop.
        return False

    # Rec. 601 luma, which tracks perceived brightness closely enough for this decision.
    luminance = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, _ in visible) / len(visible)
    return luminance >= LIGHT_INK_LUMINANCE


def _composite_on_dark(data: bytes) -> bytes:
    """The same image flattened onto a dark square, as PNG."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGBA")
        backdrop = Image.new("RGBA", image.size, (*DARK_BACKDROP, 255))
        backdrop.alpha_composite(image)
        buffer = io.BytesIO()
        backdrop.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()


class LogoProvider(ABC):
    @abstractmethod
    def get_logo(self, symbol: str, name: str) -> LogoImage | None:
        """Brand icon for an asset, or None when one can't be resolved.

        Takes the display name as well as the symbol because a fund's brand is its issuer's,
        and the issuer is named in the fund's title long before any price feed mentions it.
        """


def _domain(website: str | None) -> str | None:
    """Bare hostname of an issuer website, or None if it isn't a usable public http(s) URL."""
    if not website:
        return None
    parsed = urlparse(website if "//" in website else f"//{website}", scheme="https")
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").strip().lower()
    # Rules out "localhost", loopback/private/link-local IPs (v4 and v6) and other non-public
    # hosts reached through a symbol lookup we don't control — this fetch happens from the
    # user's own machine.
    if "." not in host or _is_private_host(host):
        return None
    return host


class WebsiteLogoProvider(LogoProvider):
    """Resolves a brand's website, then reads the icon that site publishes."""

    @staticmethod
    def _override_url(name: str) -> str | None:
        lowered = name.lower()
        for key, url in sorted(ICON_URL_OVERRIDES.items(), key=lambda kv: -len(kv[0])):
            if key in lowered:
                return url
        return None

    def _candidate_domains(self, symbol: str, name: str) -> Iterator[str]:
        """Domains to try, best-known brand first.

        A generator on purpose: the yfinance lookup at the end is a slow scrape, and an asset
        matched by one of the tables above never has to pay for it.
        """
        base_symbol = symbol.split(".")[0].upper()
        for key in (symbol.upper(), base_symbol):
            if key in SYMBOL_DOMAINS:
                yield SYMBOL_DOMAINS[key]
                break

        lowered = name.lower()
        for issuer, domain in sorted(ISSUER_DOMAINS.items(), key=lambda kv: -len(kv[0])):
            if issuer in lowered:
                yield domain
                break

        website = _domain(self._website(symbol))
        if website is not None:
            yield website

    def _website(self, symbol: str) -> str | None:
        import yfinance as yf

        try:
            return yf.Ticker(symbol).info.get("website")
        except Exception:
            # .info is a scrape: it rate-limits, changes shape and 404s on delisted symbols.
            # A missing logo is cosmetic, so every failure mode here is just "no logo".
            return None

    def _client(self) -> httpx.Client:
        # retries covers connect-level failures with backoff; a non-image answer is a real
        # answer, not a transient fault, so it falls through to the next candidate.
        transport = httpx.HTTPTransport(retries=2)
        return httpx.Client(
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": USER_AGENT},
        )

    def get_logo(self, symbol: str, name: str) -> LogoImage | None:
        try:
            with self._client() as client:
                override = self._override_url(name)
                if override:
                    image = self._try_fetch(client, override)
                    if image is not None:
                        return image

                for domain in self._candidate_domains(symbol, name):
                    image = self._best_icon(client, domain)
                    if image is not None:
                        return image
        except Exception:
            return None
        return None

    def get_logo_for_domain(self, domain: str) -> LogoImage | None:
        """The best icon a known domain publishes -- the entry point for a caller that already
        knows exactly which site to ask (gripr's bank-logo picker), skipping the symbol/name
        brand-resolution get_logo() does for assets."""
        try:
            with self._client() as client:
                return self._best_icon(client, domain)
        except Exception:
            return None

    def _best_icon(self, client: httpx.Client, domain: str) -> LogoImage | None:
        """The largest usable icon the site offers, preferring what it declares about itself.

        Guessing at conventional paths finds a 16px favicon.ico and little else — the good
        artwork is the 152px or 192px icon the page points at, usually on a CDN host under a
        content-hashed name that could never be guessed. So the page is read first, and the
        fixed paths are only what's left to try when it declares nothing.
        """
        best: LogoImage | None = None
        best_px = 0

        for fetched, candidate in enumerate(self._icon_candidates(client, domain)):
            if fetched >= MAX_CANDIDATE_FETCHES:
                break
            image = self._try_fetch(client, candidate.url)
            if image is None:
                continue
            pixels = _pixel_size(image.data, image.content_type)
            # An unmeasurable format (webp, say) is worth keeping if nothing better turned
            # up, but shouldn't outrank an icon we can see is big.
            score = pixels if pixels else MIN_USEFUL_PX - 1
            if score > best_px:
                best, best_px = image, score
            if best_px >= GOOD_ENOUGH_PX:
                break

        return best

    def _icon_candidates(self, client: httpx.Client, domain: str) -> Iterator[_Candidate]:
        declared = self._declared_icons(client, domain)
        for candidate in sorted(declared, key=lambda c: c.declared_px, reverse=True):
            yield candidate

        seen = {c.url for c in declared}
        for path in ICON_PATHS:
            url = f"https://{domain}{path}"
            if url not in seen:
                yield _Candidate(url)

    def _declared_icons(self, client: httpx.Client, domain: str) -> list[_Candidate]:
        """Icons the site's own markup points at, plus any its web manifest lists."""
        try:
            page = client.get(f"https://{domain}/")
            if page.status_code != 200:
                return []
            html = page.text
        except Exception:
            return []

        base = str(page.url)
        candidates: list[_Candidate] = []
        manifest_url: str | None = None

        for tag in re.findall(r"<link\b[^>]*>", html, re.IGNORECASE)[:200]:
            rel = re.search(r'rel=["\']([^"\']+)', tag, re.IGNORECASE)
            href = re.search(r'href=["\']([^"\']+)', tag, re.IGNORECASE)
            if not rel or not href:
                continue
            relation = rel.group(1).lower()
            # urljoin resolves relative paths and protocol-relative "//host/..." hrefs against
            # the page that was actually served, redirects included.
            target = urljoin(base, href.group(1).replace("&amp;", "&"))
            if "icon" in relation:
                sizes = re.search(r'sizes=["\']([^"\']+)', tag, re.IGNORECASE)
                candidates.append(_Candidate(target, _declared_px(sizes.group(1) if sizes else None)))
            elif "manifest" in relation and manifest_url is None:
                manifest_url = target

        if manifest_url:
            candidates.extend(self._manifest_icons(client, manifest_url))

        return [c for c in candidates if _is_fetchable(c.url)]

    @staticmethod
    def _manifest_icons(client: httpx.Client, url: str) -> list[_Candidate]:
        try:
            response = client.get(url)
            icons = json.loads(response.text).get("icons") or []
        except (httpx.HTTPError, json.JSONDecodeError, AttributeError, ValueError):
            return []
        out = []
        for icon in icons[:20]:
            src = icon.get("src") if isinstance(icon, dict) else None
            if src:
                out.append(_Candidate(urljoin(str(response.url), src), _declared_px(icon.get("sizes"))))
        return out

    def _try_fetch(self, client: httpx.Client, url: str) -> LogoImage | None:
        try:
            response = client.get(url)
        except Exception:
            return None
        if response.status_code != 200:
            return None
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        # Sites that don't have the file often answer with their 200 HTML shell rather than
        # a 404, so the content type is what actually decides whether this is an icon.
        if not content_type.startswith("image/"):
            return None
        data = response.content
        if not data or len(data) > MAX_LOGO_BYTES:
            return None
        if content_type in ("image/x-icon", "image/vnd.microsoft.icon"):
            data = _largest_ico_frame(data)
        elif _needs_dark_backdrop(data):
            # White-on-transparent artwork would be a blank square on the light tile a logo
            # sits on, so it's flattened onto a dark one here rather than at render time —
            # the stored bytes are then correct wherever the image is used.
            data, content_type = _composite_on_dark(data), "image/png"
        return LogoImage(content_type=content_type, data=data, source_url=url)
