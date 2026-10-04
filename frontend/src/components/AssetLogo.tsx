import { useState } from "react";

// Same categorical hues the allocation chart uses, picked by ticker so a given holding keeps
// the same badge colour everywhere and between sessions.
const BADGE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

function badgeColor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return BADGE_COLORS[hash % BADGE_COLORS.length];
}

/** Two-letter monogram: initials of a multi-word name, else the first letters of one word. */
function initials(name: string, ticker: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  const source = words[0] ?? ticker;
  return source.slice(0, 2).toUpperCase();
}

/** An asset's brand logo, falling back to an initials badge.
 *
 * Plenty of holdings have no findable logo (crypto pairs, delisted tickers, cash), so the
 * badge is the baseline and the image is layered over it once it actually loads — that way a
 * missing or slow logo never collapses the row's layout or flashes a broken-image glyph. */
export default function AssetLogo({
  assetId,
  name,
  ticker,
  size = 28,
}: {
  assetId: number;
  name: string;
  ticker: string;
  size?: number;
}) {
  // Which asset's image has actually painted — not a bare boolean reset by an effect. A
  // browser-cached logo fires onLoad before mount effects run, so a `setLoaded(false)` reset
  // would land *after* the load and hide the image for good; deriving it from the id instead
  // means a new asset is un-loaded by construction.
  const [loadedId, setLoadedId] = useState<number | null>(null);
  const loaded = loadedId === assetId;
  // CASH is a synthetic row with no asset behind it, so there's nothing to ask the API for.
  const hasSource = assetId > 0;

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md text-[10px] font-semibold text-white"
      style={{ width: size, height: size, backgroundColor: badgeColor(ticker || name) }}
      aria-hidden
    >
      {!loaded && <span>{initials(name, ticker)}</span>}
      {hasSource && (
        <img
          src={`/api/assets/${assetId}/logo`}
          alt=""
          loading="lazy"
          onLoad={() => setLoadedId(assetId)}
          onError={() => setLoadedId(null)}
          className={`absolute inset-0 h-full w-full bg-white object-contain transition-opacity ${
            loaded ? "opacity-100" : "opacity-0"
          }`}
        />
      )}
    </span>
  );
}
