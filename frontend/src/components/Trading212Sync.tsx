import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { api } from "../api/client";
import { griprApi } from "../api/griprClient";
import type { Asset, BrokerStatus, BrokerSyncResult, BrokerUnmapped, SymbolMatch } from "../api/types";
import { formatDate, formatRelativeTime } from "../utils/format";
import AssetCombobox from "./AssetCombobox";
import AssetSymbolPicker from "./AssetSymbolPicker";
import InfoHeading from "./ui/InfoTip";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "./ui/kit";
import SettingsSection from "./ui/SettingsSection";
import SyncButton from "./ui/SyncButton";
import { t, tp } from "../i18n";

/** Trading 212's own ticker ("GRIDd_EQ", "AMZN_US_EQ") as a starting point for a new asset's:
 * the exchange suffix and Trading 212's lowercase listing letter dropped. */
function suggestedTicker(t212Ticker: string): string {
  return t212Ticker.split("_")[0].replace(/[a-z]+$/, "") || t212Ticker;
}

function describeResult(r: BrokerSyncResult): string {
  const parts = [
    r.booked && t("{n} booked", { n: r.booked }),
    r.matched && t("{n} already in gainr", { n: r.matched }),
    r.deposits && tp(r.deposits, "{n} weekly interest row", "{n} weekly interest rows"),
    r.cashbacks && t("{n} weekly cashback in gripr", { n: r.cashbacks }),
  ].filter(Boolean);
  const head = parts.length ? `${parts.join(", ")}.` : t("Nothing new from Trading 212.");
  return [head, ...r.problems].join(" ");
}

/** gainr's Trading 212 sync (docs/adr/0031), on the Transactions page it books into: on/off from
 * a start date for the portfolio being viewed, "Sync now", and the instruments it's holding back
 * because no asset has their ISIN yet -- each linked to an existing asset or a new one right
 * here. */
export default function Trading212Sync({
  portfolioId,
  portfolioName,
  defaultOpen = false,
}: {
  portfolioId: number;
  portfolioName: string;
  defaultOpen?: boolean;
}) {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({ queryKey: ["trading212"], queryFn: api.getTrading212 });
  const assetsQuery = useQuery({ queryKey: ["assets"], queryFn: api.listAssets });
  const portfoliosQuery = useQuery({ queryKey: ["portfolios"], queryFn: () => api.listPortfolios() });
  const griprAccountsQuery = useQuery({ queryKey: ["gripr-accounts", false], queryFn: () => griprApi.listAccounts() });
  const [feedback, setFeedback] = useState<string | null>(null);
  const [open, setOpen] = useState(defaultOpen);

  const setStatus = (status: BrokerStatus) => queryClient.setQueryData(["trading212"], status);
  const settingsMutation = useMutation({
    mutationFn: (input: { enabled: boolean; since?: string | null; cashback_account_id?: number | null }) =>
      api.updateTrading212({ ...input, portfolio_id: portfolioId }),
    onSuccess: setStatus,
    onError: () => setFeedback(t("Saving didn't work. Try again in a moment.")),
  });
  const syncMutation = useMutation({
    mutationFn: api.syncTrading212,
    onSuccess: (result) => {
      setFeedback(describeResult(result));
      setOpen(true); // the result is in the body
      for (const key of ["trading212", "transactions", "summary", "positions", "performance"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
    onError: () => {
      setFeedback(t("Syncing didn't work. Try again in a moment."));
      setOpen(true);
      queryClient.invalidateQueries({ queryKey: ["trading212"] });
    },
  });
  const linked = () => {
    queryClient.invalidateQueries({ queryKey: ["assets"] });
    queryClient.invalidateQueries({ queryKey: ["trading212"] });
    setFeedback(t("Linked. Its transactions are booked on the next sync — or sync now."));
  };

  const attention = !!statusQuery.data && (statusQuery.data.unmapped.length > 0 || !!statusQuery.data.last_error);
  useEffect(() => {
    if (attention) setOpen(true); // something to link or fix: don't leave it folded away
  }, [attention]);

  const info = t(
    "Fills, dividends, and one deposit a week for the interest and cashback Trading 212 pays are booked here every morning. Ones you already entered are recognised, not booked twice.",
  );
  const section = (body: ReactNode, extras: { meta?: ReactNode; actions?: ReactNode } = {}) => (
    <SettingsSection title="Trading 212" info={info} tone="gainr" open={open} onOpenChange={setOpen} {...extras}>
      {body}
    </SettingsSection>
  );

  if (statusQuery.isLoading) {
    return section(<p className="text-sm text-slate-500">{t("Loading the Trading 212 sync…")}</p>);
  }
  if (statusQuery.isError || !statusQuery.data) {
    return section(<p className="text-sm text-red-600">{t("Couldn't load the Trading 212 sync. Reload the page to try again.")}</p>);
  }
  const status = statusQuery.data;
  if (!status.configured && !status.enabled) {
    return section(<p className="text-sm text-slate-500">{t("Trading 212 isn't set up on this server, so there's nothing to switch on.")}</p>);
  }

  const elsewhere = status.enabled && status.portfolio_id !== null && status.portfolio_id !== portfolioId;
  const targetName = portfoliosQuery.data?.find((p) => p.id === status.portfolio_id)?.name ?? t("another portfolio");
  const busy = settingsMutation.isPending || syncMutation.isPending;
  const needsAttention = status.unmapped.length > 0 || !!status.last_error;
  const meta = (
    <span className={`text-xs ${status.last_error ? "font-medium text-red-600" : needsAttention ? "font-medium text-slate-700" : "text-slate-500"}`}>
      {status.unmapped.length > 0
        ? t("{n} to link", { n: status.unmapped.length })
        : status.last_error
          ? t("Needs attention")
          : status.enabled && status.last_synced_at
            ? t("Synced {when}", { when: formatRelativeTime(status.last_synced_at) })

            : status.enabled
              ? t("On")
              : t("Off")}
    </span>
  );

  const syncAction =
    status.enabled && !elsewhere ? (
      <SyncButton
        tone="gainr"
        pending={syncMutation.isPending}
        disabled={busy || !status.configured}
        pendingLabel={t("Syncing… Trading 212 can take a minute or two to hand over its records.")}
        onClick={() => syncMutation.mutate()}
      />
    ) : null;

  return section(
    (
      <div className="flex flex-col gap-3 text-sm">
        {!status.configured && (
          <p className="text-red-600">{t("The Trading 212 API key is missing on the server, so nothing syncs right now.")}</p>
        )}
        {status.last_error && <p className="text-red-600">{status.last_error}</p>}

        {elsewhere ? (
          <p className="text-slate-600">{t("Books into")}{" "}<span className="font-medium">{targetName}</span>{t(". Switch to it to change the sync.")}</p>
        ) : (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <label className="flex items-center gap-2 text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={status.enabled}
                disabled={busy || !status.configured}
                onChange={(e) => settingsMutation.mutate({ enabled: e.target.checked, since: status.since })}
              />{t("Book Trading 212 into {portfolioName}", { portfolioName: portfolioName })}</label>
            <label className="flex items-center gap-2 text-slate-500">{t("from")}<input
                type="date"
                aria-label={t("Trading 212 start date")}
                value={status.since ?? ""}
                disabled={busy}
                onChange={(e) => e.target.value && settingsMutation.mutate({ enabled: status.enabled, since: e.target.value })}
                className={`${inputClass} sm:w-44`}
              />
            </label>
          </div>
        )}

        {!elsewhere && (
          <label className="flex flex-col gap-1 text-slate-700 sm:flex-row sm:items-center sm:gap-3">
            <span className="shrink-0">{t("Weekly cashback goes to")}</span>
            <select
              aria-label={t("Cashback account")}
              value={status.cashback_account_id ?? ""}
              disabled={busy}
              onChange={(e) =>
                settingsMutation.mutate({
                  enabled: status.enabled,
                  since: status.since,
                  cashback_account_id: e.target.value === "" ? null : Number(e.target.value),
                })
              }
              className={`${inputClass} sm:flex-1`}
            >
              <option value="">{t("Nowhere: part of the weekly deposit here")}</option>
              {(griprAccountsQuery.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}{" "}{t("(gripr)")}</option>
              ))}
            </select>
          </label>
        )}

        {status.unmapped.length > 0 && (
          <section aria-label={t("Instruments to link")} className="flex flex-col gap-2">
            <InfoHeading
              label={t("Waiting for an asset")}
              title={<h3 className="font-medium text-slate-700">{t("Waiting for an asset")}</h3>}
              textClassName="text-xs text-slate-500"
              buttonClassName="text-slate-400 hover:text-slate-600"
            >{t("No asset has these ISINs yet, so their transactions are held back. Pick the asset each one is, or add it.")}</InfoHeading>
            <ul className="flex flex-col gap-3">
              {status.unmapped.map((item) => (
                <UnmappedRow key={item.isin} item={item} assets={assetsQuery.data ?? []} onLinked={linked} />
              ))}
            </ul>
          </section>
        )}

        {feedback && (
          <p role="status" className="rounded-md bg-slate-50 px-3 py-2 text-slate-700">
            {feedback}
          </p>
        )}
      </div>
    ),
    { meta, actions: syncAction },
  );
}

function UnmappedRow({ item, assets, onLinked }: { item: BrokerUnmapped; assets: Asset[]; onLinked: () => void }) {
  const [adding, setAdding] = useState(false);
  const [ticker, setTicker] = useState(suggestedTicker(item.ticker));
  const [symbol, setSymbol] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const holdable = assets.filter((a) => a.asset_class !== "fx" && a.asset_class !== "benchmark");

  const linkMutation = useMutation({
    mutationFn: (assetId: number) => api.updateAsset(assetId, { isin: item.isin }),
    onSuccess: onLinked,
    onError: () => setError(t("Linking didn't work.")),
  });
  const createMutation = useMutation({
    mutationFn: () =>
      api.createAsset({
        ticker: ticker.trim(),
        name: item.name,
        asset_class: "equity",
        native_currency: item.currency || "EUR",
        yahoo_symbol: symbol,
        isin: item.isin,
      }),
    onSuccess: onLinked,
    onError: () => setError(t("Adding the asset didn't work.")),
  });

  return (
    <li className="flex flex-col gap-2 rounded-md border border-slate-200 p-3">
      <div className="min-w-0">
        <div className="truncate font-medium text-slate-800">{item.name}</div>
        <div className="text-xs text-slate-500">
          {item.ticker} · {item.isin} · {item.records} {item.records === 1 ? "record" : "records"}{" "}{t("since {firstdate}", { firstdate: formatDate(item.first_date) })}</div>
      </div>
      {adding ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <input aria-label={t("New asset ticker")} value={ticker} onChange={(e) => setTicker(e.target.value)} className={inputClass} />
          <AssetSymbolPicker ticker={ticker} value={symbol} onChange={(next: string | null, _match: SymbolMatch | null) => setSymbol(next)} />
          <div className="flex gap-2">
            <button type="submit" className={primaryButtonClass} disabled={!ticker.trim() || createMutation.isPending}>{t("Add")}{" "}{ticker.trim() || "asset"}
            </button>
            <button type="button" className={secondaryButtonClass} onClick={() => setAdding(false)}>{t("Cancel")}</button>
          </div>
        </form>
      ) : (
        <AssetCombobox
          assets={holdable}
          value={null}
          onChange={(assetId) => linkMutation.mutate(assetId)}
          onAddNew={() => setAdding(true)}
          placeholder={t("This is…")}
        />
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </li>
  );
}
