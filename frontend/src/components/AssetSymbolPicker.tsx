import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { SymbolMatch } from "../api/types";

const DEBOUNCE_MS = 400;

/** "Price from": the listings Yahoo knows for the ticker being typed, one of which becomes the new
 * asset's price symbol. A bare ticker often isn't one (IQQW only exists as IQQW.DE, IQQW.MU, …),
 * and when it is, it may be a different fund altogether (plain TDIV is an American First Trust
 * fund; the VanEck one is TDIV.AS) -- so every listing is shown with its exchange and full name,
 * and the reader sees which fund they're picking. The exact ticker is pre-picked when it's a
 * listing, else the first one. */
export default function AssetSymbolPicker({
  ticker,
  value,
  onChange,
}: {
  ticker: string;
  value: string | null;
  onChange: (symbol: string | null, match: SymbolMatch | null) => void;
}) {
  const [query, setQuery] = useState(ticker.trim());
  useEffect(() => {
    const id = setTimeout(() => setQuery(ticker.trim()), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [ticker]);

  const lookup = useQuery({
    queryKey: ["asset-lookup", query],
    queryFn: () => api.lookupAsset(query),
    enabled: query.length >= 2,
    staleTime: 10 * 60_000,
    retry: false,
  });
  const matches = lookup.data?.query === query ? lookup.data.matches : undefined;

  // Pre-pick once results arrive, and whenever the current pick isn't among them any more.
  useEffect(() => {
    if (!matches) return;
    if (value !== null && matches.some((m) => m.symbol === value)) return;
    const pick = matches.find((m) => m.symbol.toUpperCase() === query.toUpperCase()) ?? matches[0] ?? null;
    onChange(pick?.symbol ?? null, pick);
  }, [matches, value, query, onChange]);

  if (query.length < 2) return null;
  if (lookup.isError) {
    return <p className="text-xs text-amber-700">Couldn't reach Yahoo to check this ticker — it'll be used as typed.</p>;
  }
  if (!matches) {
    return <p className="text-xs text-slate-500">Looking up “{query}” on Yahoo…</p>;
  }
  if (matches.length === 0) {
    return (
      <p className="text-xs text-amber-700">
        Yahoo doesn't know “{query}”, so gainr won't find a price for it. Try the exchange's ticker with a suffix (like
        IQQW.DE), the fund's ISIN, or its name.
      </p>
    );
  }
  return (
    // min-w-0: a fieldset is as wide as its content by default, which would widen the form column.
    <fieldset className="flex min-w-0 flex-col gap-1">
      <legend className="mb-1 text-xs font-medium text-slate-600">Price from</legend>
      <div className="flex max-h-44 flex-col gap-1 overflow-y-auto">
        {matches.map((m) => (
          <label
            key={m.symbol}
            className={`flex cursor-pointer items-start gap-2 rounded-md border px-2 py-1.5 text-xs ${
              value === m.symbol ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:bg-slate-50"
            }`}
          >
            <input
              type="radio"
              name="asset-symbol"
              className="mt-0.5"
              checked={value === m.symbol}
              onChange={() => onChange(m.symbol, m)}
            />
            <span className="min-w-0">
              <span className="text-slate-500">
                <span className="font-medium text-slate-900">{m.symbol}</span> · {m.exchange || "?"}
              </span>
              {m.name && <span className="block break-words text-slate-600">{m.name}</span>}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
