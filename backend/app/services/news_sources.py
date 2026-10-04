"""Extra news feeds a position can pull in besides its own ticker's -- for holdings whose own
symbol has little or no news (an ETF, a gold tracker). See docs/adr/0026.

A source is a string key:
- "sector:<key>"   -- a Yahoo sector, e.g. "sector:utilities"
- "industry:<key>" -- a Yahoo industry, e.g. "industry:aerospace-defense"
- "ticker:<sym>"   -- any Yahoo symbol, e.g. "ticker:GC=F" (gold futures) or "ticker:BTC-USD"

yfinance's `Market` class (commodities, cryptocurrencies) was the first idea for the last two,
but it only returns a status summary with one arbitrary highlight symbol per exchange (Brent
and copper for commodities, Solana for crypto) -- no news. The main futures contract or USD
pair's own news is the market-wide feed in practice, so those are offered as ticker sources.
"""

import json
import re

import yfinance.const as yf_const

_SYMBOL = re.compile(r"^[A-Za-z0-9.=^\-]{1,20}$")
MAX_SOURCES = 6

# Suggested ticker sources for the markets the Market class can't supply news for.
MARKET_SOURCES = [
    ("ticker:GC=F", "Gold (futures)"),
    ("ticker:SI=F", "Silver (futures)"),
    ("ticker:CL=F", "Crude oil (futures)"),
    ("ticker:BTC-USD", "Bitcoin (crypto market)"),
    ("ticker:ETH-USD", "Ethereum (crypto market)"),
]


def _key(name: str) -> str:
    """Yahoo's sector/industry key for a display name: "Aerospace & Defense" ->
    "aerospace-defense". yfinance's own lowercase table spells a few with an em-dash
    ("utilities—renewable") that Yahoo's API rejects, so keys are derived from the names."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", ""))).strip("-")


def _pretty(name: str) -> str:
    return name.replace("—", " – ")


SECTORS: dict[str, str] = {_key(name): name for name in yf_const.SECTOR_INDUSTY_MAPPING}
# industry key -> (display name, sector key)
INDUSTRIES: dict[str, tuple[str, str]] = {
    _key(industry): (_pretty(industry), _key(sector))
    for sector, industries in yf_const.SECTOR_INDUSTY_MAPPING.items()
    for industry in industries
}


class InvalidNewsSource(ValueError):
    pass


def label(source: str) -> str:
    kind, _, value = source.partition(":")
    if kind == "sector":
        return SECTORS.get(value, value)
    if kind == "industry":
        return INDUSTRIES.get(value, (value, ""))[0]
    return dict(MARKET_SOURCES).get(source, value)


def validate(sources: list[str]) -> list[str]:
    """The given keys, de-duplicated in order -- or InvalidNewsSource naming the first bad one."""
    cleaned: list[str] = []
    for source in sources:
        kind, _, value = source.strip().partition(":")
        ok = (
            (kind == "sector" and value in SECTORS)
            or (kind == "industry" and value in INDUSTRIES)
            or (kind == "ticker" and bool(_SYMBOL.match(value)))
        )
        if not ok:
            raise InvalidNewsSource(f"Unknown news source: {source!r}")
        normalized = f"{kind}:{value.upper() if kind == 'ticker' else value}"
        if normalized not in cleaned:
            cleaned.append(normalized)
    if len(cleaned) > MAX_SOURCES:
        raise InvalidNewsSource(f"At most {MAX_SOURCES} extra news sources per position")
    return cleaned


def parse_stored(raw: str | None) -> list[str]:
    """An asset's stored sources; anything unreadable counts as none rather than failing a page."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [s for s in value if isinstance(s, str)] if isinstance(value, list) else []


def catalog() -> dict:
    return {
        "markets": [{"key": k, "label": v} for k, v in MARKET_SOURCES],
        "sectors": [{"key": f"sector:{k}", "label": v} for k, v in sorted(SECTORS.items(), key=lambda i: i[1])],
        "industries": [
            {"key": f"industry:{k}", "label": name, "sector": SECTORS.get(sector, sector)}
            for k, (name, sector) in sorted(INDUSTRIES.items(), key=lambda i: (SECTORS.get(i[1][1], ""), i[1][0]))
        ],
    }
