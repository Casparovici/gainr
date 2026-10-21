import { useQuery } from "@tanstack/react-query";

import { griprApi } from "../../api/griprClient";
import { formatEur } from "../../utils/format";
import InfoHeading from "../ui/InfoTip";
import { t } from "../../i18n";

/** The cars (or other manually valued assets) losing value through a monthly transfer, next to the
 * fund that transfer fills (docs/adr/0034). The fund follows the market, the asset follows the
 * plan; this shows how far one covers the other. Hidden until a transfer is set up as a
 * depreciation. */
export default function DepreciationCard() {
  const query = useQuery({ queryKey: ["gripr-depreciation"], queryFn: () => griprApi.getDepreciation() });
  if (query.isLoading) return null;
  if (query.isError || !query.data) {
    return <p className="text-sm text-error">{t("Couldn't load the depreciation. Reload the page to try again.")}</p>;
  }
  const { assets, funds } = query.data;
  if (assets.length === 0) return null;

  return (
    <section className="rounded-2xl border border-outline-variant bg-surface px-4 py-3" aria-label={t("Depreciation")}>
      <InfoHeading label={t("Depreciation")} title={<span className="text-sm text-on-surface-variant">{t("Depreciation")}</span>}>{t("What your assets lose each month through a recurring transfer into a fund. The asset's value follows this plan, not the market; the fund follows the market. \"Covers\" is the fund's balance as a share of the value that's depreciating into it.")}</InfoHeading>
      <ul className="mt-2 divide-y divide-outline-variant">
        {assets.map((a) => (
          <li key={a.account_id} className="flex items-center justify-between gap-3 py-2 text-sm">
            <span className="min-w-0 truncate text-on-surface">{a.name}</span>
            <span className="shrink-0 text-right">
              <span className="tabular-nums text-on-surface">{formatEur(a.value)}</span>
              <span className="block text-xs text-on-surface-variant">
                −{formatEur(a.monthly)}{" "}{t("a month")}{a.months_left !== null && a.months_left > 0 ? ` · ${t("{n} months left", { n: a.months_left })}` : ""}
              </span>
            </span>
          </li>
        ))}
      </ul>
      {funds.map((f) => (
        <div key={f.account_id} className="mt-1 flex items-baseline justify-between gap-3 border-t border-outline-variant pt-2 text-sm">
          <span className="text-on-surface-variant">
            {f.name} <span className="tabular-nums text-on-surface">{formatEur(f.balance)}</span>
          </span>
          {f.covers_pct !== null && <span className="text-xs text-on-surface-variant">{t("covers {pct}% of the value", { pct: Number(f.covers_pct).toFixed(1).replace(".", ",") })}</span>}
        </div>
      ))}
    </section>
  );
}
