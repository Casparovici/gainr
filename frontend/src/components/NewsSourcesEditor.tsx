import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { NewsSource } from "../api/types";
import { t } from "../i18n";

const OTHER_SYMBOL = "__other_symbol__";

const inputClass =
  "rounded-md border border-slate-300 px-2 py-1 text-xs focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

/** The position's extra news feeds -- a sector, an industry or any Yahoo symbol -- shown as
 * removable chips with an add control. For holdings whose own ticker has little news: a gold
 * tracker reading gold-futures news, a defence ETF reading its industry's. See docs/adr/0026. */
export default function NewsSourcesEditor({ assetId, sources }: { assetId: number; sources: NewsSource[] }) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [symbol, setSymbol] = useState<string | null>(null); // non-null = typing a custom symbol
  const [error, setError] = useState<string | null>(null);

  const catalogQuery = useQuery({
    queryKey: ["news-source-catalog"],
    queryFn: api.getNewsSourceCatalog,
    enabled: adding,
    staleTime: Infinity,
  });
  const mutation = useMutation({
    mutationFn: (next: string[]) => api.updateNewsSources(assetId, next),
    onSuccess: (news) => {
      // The response already is the news with the new sources applied.
      queryClient.setQueryData(["asset-news", assetId], news);
      setAdding(false);
      setSymbol(null);
      setError(null);
    },
    onError: () => setError(t("Couldn't save that source.")),
  });

  const keys = sources.map((s) => s.key);
  const add = (key: string) => {
    if (!keys.includes(key)) mutation.mutate([...keys, key]);
    else setAdding(false);
  };
  const catalog = catalogQuery.data;
  const industriesBySector = new Map<string, NewsSource[]>();
  for (const i of catalog?.industries ?? []) {
    industriesBySector.set(i.sector, [...(industriesBySector.get(i.sector) ?? []), i]);
  }

  return (
    <div className="mb-3 flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-slate-500">{sources.length > 0 ? t("Also from:") : t("Only this holding's own news.")}</span>
        {sources.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1 rounded-full bg-slate-100 py-0.5 pl-2 pr-1 text-slate-700">
            {s.label}
            <button
              type="button"
              onClick={() => mutation.mutate(keys.filter((k) => k !== s.key))}
              disabled={mutation.isPending}
              className="rounded-full p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
              aria-label={t("Stop showing news from {source}", { source: s.label })}
              title={t("Remove")}
            >
              <X className="h-3 w-3" strokeWidth={2.5} />
            </button>
          </span>
        ))}
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-slate-500 hover:border-slate-400 hover:text-slate-800"
          >{t("+ Add source")}</button>
        )}
      </div>

      {adding && (
        <div className="flex flex-wrap items-center gap-1.5">
          {symbol === null ? (
            <select
              autoFocus
              aria-label={t("News source")}
              defaultValue=""
              disabled={!catalog || mutation.isPending}
              onChange={(e) => (e.target.value === OTHER_SYMBOL ? setSymbol("") : add(e.target.value))}
              className={`${inputClass} max-w-full`}
            >
              <option value="" disabled>
                {catalog ? t("Pick a market, sector or industry…") : catalogQuery.isError ? t("Couldn't load sources") : t("Loading…")}
              </option>
              {catalog && (
                <>
                  <optgroup label={t("Markets")}>
                    {catalog.markets.map((m) => (
                      <option key={m.key} value={m.key}>
                        {m.label}
                      </option>
                    ))}
                    <option value={OTHER_SYMBOL}>{t("Other Yahoo symbol…")}</option>
                  </optgroup>
                  <optgroup label={t("Sectors")}>
                    {catalog.sectors.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </optgroup>
                  {[...industriesBySector.entries()].map(([sector, industries]) => (
                    <optgroup key={sector} label={t("Industries · {sector}", { sector })}
>
                      {industries.map((i) => (
                        <option key={i.key} value={i.key}>
                          {i.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </>
              )}
            </select>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (symbol.trim()) add(`ticker:${symbol.trim()}`);
              }}
              className="flex items-center gap-1.5"
            >
              <input
                autoFocus
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder={t("e.g. GC=F, ^GSPC, NVDA")}
                aria-label={t("Yahoo symbol")}
                className={`${inputClass} w-40`}
              />
              <button type="submit" disabled={!symbol.trim() || mutation.isPending} className="text-xs font-medium text-slate-700 hover:text-slate-900 disabled:opacity-40">{t("Add")}</button>
            </form>
          )}
          <button
            type="button"
            onClick={() => {
              setAdding(false);
              setSymbol(null);
              setError(null);
            }}
            className="text-xs text-slate-500 hover:text-slate-800"
          >{t("Cancel")}</button>
        </div>
      )}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
