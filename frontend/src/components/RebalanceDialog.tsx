import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { RebalanceLeftOut } from "../api/types";
import { formatEur, formatPct, formatQuantity, toNumber } from "../utils/format";
import DltBadge from "./DltBadge";
import ModalOverlay from "./ModalOverlay";
import { inputClass } from "./ui/kit";
import { msg, t } from "../i18n";

const DEBOUNCE_MS = 300;

const LEFT_OUT_LABELS: Record<RebalanceLeftOut["reason"], string> = {
  critical: msg("Rated Critical by DLT"),
  unrated: msg("Not rated by DLT"),
  no_target: msg("No target set"),
};

/** Names as the end of a sentence: one full stop, also after "Nu Holdings Ltd.". */
function nameList(names: string[]): string {
  const text = names.join(", ");
  return text.endsWith(".") ? text : `${text}.`;
}

/** Parses "500", "1.250,50" or "1250.5" into a plain "1250.50"; null for anything else. */
export function parseAmount(text: string): string | null {
  const cleaned = text.trim().replace(/\s|€/g, "");
  if (!cleaned) return null;
  // A comma followed by one or two digits at the end is the decimal separator (Dutch style).
  const normalised = /,\d{1,2}$/.test(cleaned) ? cleaned.replace(/\./g, "").replace(",", ".") : cleaned.replace(/,/g, "");
  if (!/^\d+(\.\d{1,2})?$/.test(normalised)) return null;
  const value = Number(normalised);
  return value > 0 ? value.toFixed(2) : null;
}

/** "Invest €X": how to spread an amount over the holdings below their target weight, buying only
 * and only what DLT rates Attractive or Neutral (docs/adr/0041 and its addendum). New money grows
 * the portfolio by the amount; cash already in it doesn't. The backend does the arithmetic --
 * this only asks and shows. */
export default function RebalanceDialog({
  portfolioId,
  cashEur,
  onClose,
}: {
  portfolioId: number;
  /** The portfolio's cash, for the "From cash" label before a plan has loaded. */
  cashEur?: string;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [fromCash, setFromCash] = useState(false);
  const [amount, setAmount] = useState<string | null>(null);
  useEffect(() => {
    const id = setTimeout(() => setAmount(parseAmount(text)), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [text]);

  const planQuery = useQuery({
    queryKey: ["rebalance", portfolioId, amount, fromCash],
    queryFn: () => api.getRebalancePlan(portfolioId, amount!, fromCash),
    enabled: amount !== null,
    placeholderData: (previous) => previous,
    retry: false,
  });
  const plan = planQuery.data;
  const buying = plan?.purchases.filter((p) => (toNumber(p.amount_eur) ?? 0) > 0) ?? [];
  const skipped = plan?.purchases.filter((p) => (toNumber(p.amount_eur) ?? 0) === 0) ?? [];
  const tooMuchCash = planQuery.isError && planQuery.error.message.startsWith("400");
  const cash = plan?.cash_eur ?? cashEur;

  return (
    <ModalOverlay onClose={onClose} cardClassName="flex max-h-[90vh] w-full max-w-lg flex-col rounded-lg bg-white shadow-lg">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-900">{t("Rebalance")}</h2>
        <button type="button" onClick={onClose} className="text-sm font-medium text-slate-500 hover:text-slate-800">{t("Close")}</button>
      </div>

      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-5 py-4">
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Amount to invest")}</span>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              inputMode="decimal"
              placeholder={t("e.g. 500")}
              autoFocus
              className={inputClass}
            />
          </label>
          <div className="flex rounded-xl border border-ui-border p-1 text-sm font-semibold" role="group" aria-label={t("Where the money comes from")}>
            {[
              { cash: false, label: t("New money") },
              { cash: true, label: cash !== undefined ? t("From cash ({amount})", { amount: formatEur(cash) }) : t("From cash")
 },
            ].map((o) => (
              <button
                key={String(o.cash)}
                type="button"
                aria-pressed={fromCash === o.cash}
                onClick={() => setFromCash(o.cash)}
                className={`flex-1 rounded-lg px-3 py-2 ${fromCash === o.cash ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted hover:text-ui-ink"}`}
              >
                {o.label}
              </button>
            ))}
          </div>
          <p className="m-0 text-xs text-ui-muted">{t("Split over the holdings below their target that DLT rates Attractive or Neutral, the furthest behind getting the most. Nothing is sold.")}</p>
        </div>

        {amount === null ? (
          <p className="m-0 text-sm text-ui-muted">{text.trim() ? t("Enter an amount in euros, like 500 or 1.250,50.") : t("Enter an amount to see what to buy.")}</p>
        ) : planQuery.isPending ? (
          <p className="m-0 text-sm text-ui-muted" role="status">{t("Working it out…")}</p>
        ) : tooMuchCash ? (
          <p className="m-0 text-sm text-ui-late" role="alert">{t("That's more than the")}{" "}{cash !== undefined ? formatEur(cash) : t("cash")}{" "}{t("in cash — lower the amount, or choose new money.")}</p>
        ) : planQuery.isError ? (
          <p className="m-0 text-sm text-ui-late" role="alert">{t("Couldn't work out a plan.")}{" "}
            <button type="button" onClick={() => planQuery.refetch()} className="font-semibold underline">{t("Try again")}</button>
          </p>
        ) : (
          plan && (
            <div className={`flex flex-col gap-3 ${planQuery.isPlaceholderData ? "opacity-60" : ""}`}>
              {buying.length === 0 ? (
                <p className="m-0 text-sm text-ui-muted">{t("No holding rated Attractive or Neutral has a target to buy towards.")}</p>
              ) : (
                <ul className="m-0 flex list-none flex-col p-0" aria-label={t("What to buy")}>
                  {buying.map((p) => (
                    <li key={p.asset_id} className="flex items-center justify-between gap-3 border-b border-ui-border py-2.5 last:border-0">
                      <div className="flex min-w-0 flex-col gap-0.5">
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate text-[15px] font-semibold text-ui-ink">{p.asset_id === 0 ? t("Keep as cash") : p.name}</span>
                          {p.asset_id !== 0 && <DltBadge judgment={p.dlt_judgment} unrated="none" />}
                        </span>
                        <span className="text-xs tabular-nums text-ui-muted">
                          {formatPct(p.weight_before_pct, 1, false)} → {formatPct(p.weight_after_pct, 1, false)}{" "}{t("· target {targetpct}", { targetpct: formatPct(p.target_pct, 1, false) })}</span>
                      </div>
                      <div className="flex shrink-0 flex-col items-end tabular-nums">
                        <span className="text-[15px] font-semibold text-ui-ink">{formatEur(p.amount_eur)}</span>
                        {p.quantity !== null && (
                          <span className="text-xs text-ui-muted">
                            ≈ {formatQuantity(p.quantity, 3)} {p.ticker}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {skipped.length > 0 && (
                <p className="m-0 text-xs text-ui-muted">{t("At or over target, so nothing:")}{" "}{nameList(skipped.map((p) => (p.asset_id === 0 ? t("cash") : p.name)))}
                </p>
              )}
              {(["critical", "unrated", "no_target"] as const).map((reason) => {
                const names = plan.left_out.filter((h) => h.reason === reason).map((h) => h.name);
                return (
                  names.length > 0 && (
                    <p key={reason} className="m-0 text-xs text-ui-muted">
                      {t(LEFT_OUT_LABELS[reason])}{t(", so left out:")}{" "}{nameList(names)}
                    </p>
                  )
                );
              })}
            </div>
          )
        )}
      </div>
    </ModalOverlay>
  );
}
