import { useQuery } from "@tanstack/react-query";

import { griprApi } from "../../api/griprClient";
import { formatEur, toNumber } from "../../utils/format";
import { t } from "../../i18n";

/** A top-level category's spending in a period, split by the subcategory it was filed under. What
 * was filed straight on the category is shown as its own row, so the rows always add up to the
 * category's total. Clicking a subcategory hands it to `onSelect` (the dialog narrows its
 * transactions to it); with no `onSelect` the rows are plain. */
export default function SubcategoryBreakdown({
  categoryId,
  period,
  color,
  selectedId = null,
  onSelect,
}: {
  categoryId: number;
  period: string;
  color: string;
  selectedId?: number | null;
  onSelect?: (subcategoryId: number | null) => void;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["gripr-subcategories", categoryId, period],
    queryFn: () => griprApi.getSubcategoryBreakdown(categoryId, period),
  });

  if (isLoading) return <p className="text-sm text-on-surface-variant">{t("Loading…")}</p>;
  if (isError || !data) return <p className="text-sm text-on-surface-variant">{t("Couldn't load the subcategories.")}</p>;
  if (data.length === 0) return <p className="text-sm text-on-surface-variant">{t("Nothing spent in this category this period.")}</p>;

  const rows = data.map((r) => ({ id: r.category_id, name: r.name, amount: toNumber(r.amount) ?? 0, isParent: r.category_id === categoryId }));
  const total = rows.reduce((sum, r) => sum + r.amount, 0);
  const max = Math.max(...rows.map((r) => r.amount));
  const sorted = rows.some((r) => !r.isParent);

  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {rows.map((r) => {
          const selected = selectedId === r.id && !r.isParent;
          const content = (
            <>
              <span className="flex items-baseline justify-between gap-2 text-sm">
                <span className={`truncate ${r.isParent ? "text-on-surface-variant" : "text-on-surface"} ${selected ? "font-medium" : ""}`}>
                  {r.isParent ? t("Not in a subcategory") : r.name}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-on-surface-variant">
                  <span className="text-on-surface">{formatEur(r.amount)}</span> · {Math.round((r.amount / total) * 100)}%
                </span>
              </span>
              <span className="mt-1 block h-2 overflow-hidden rounded-full bg-surface-container-high">
                <span
                  className="block h-full rounded-full"
                  style={{ width: `${(r.amount / max) * 100}%`, backgroundColor: color, opacity: r.isParent ? 0.4 : 1 }}
                />
              </span>
            </>
          );
          return (
            <li key={r.id}>
              {onSelect && !r.isParent ? (
                <button type="button" onClick={() => onSelect(selected ? null : r.id)} aria-pressed={selected} className="block w-full rounded text-left hover:bg-on-surface/5">
                  {content}
                </button>
              ) : (
                content
              )}
            </li>
          );
        })}
      </ul>
      {!sorted && (
        <p className="text-xs text-on-surface-variant">{t("Nothing is filed under a subcategory yet. Pick one when you add or edit a transaction to see the split here.")}</p>
      )}
    </div>
  );
}
