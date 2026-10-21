import type { Transaction } from "../api/types";
import { formatCurrency, formatDate, formatEur, formatQuantity } from "../utils/format";
import { primaryButtonClass, secondaryButtonClass } from "./ui/kit";
import Sheet from "./ui/Sheet";
import { t as tr } from "../i18n";

/** One gainr transaction, opened from its row: what it was, and the actions on it. Edit,
 * Duplicate and Delete live here rather than as icons on every row of the list. */
export default function TransactionSheet({
  transaction: t,
  onClose,
  onEdit,
  onDuplicate,
  onDelete,
  onOpenPosition,
}: {
  transaction: Transaction;
  onClose: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  /** Opens the holding on Home; absent for a cash-only transaction. */
  onOpenPosition?: () => void;
}) {
  const fields: [string, string][] = [];
  if (t.quantity) fields.push([tr("Quantity"), formatQuantity(t.quantity)]);
  if (t.price) fields.push([tr("Price"), formatCurrency(t.price, t.native_currency)]);
  if (t.fx_rate && t.native_currency && t.native_currency !== "EUR") fields.push([tr("FX rate"), t.fx_rate]);
  fields.push([tr("Value"), formatEur(t.value_eur)]);
  fields.push([tr("Costs"), formatEur(t.costs)]);
  if (t.broker) fields.push([t.to_broker ? tr("From") : tr("Broker"), t.broker]);
  if (t.to_broker) fields.push([tr("To"), t.to_broker]);
  if (t.attachment_count) fields.push([tr("Attachments"), String(t.attachment_count)]);

  return (
    <Sheet
      title={`${tr(t.type)} · ${formatDate(t.date)}`}
      onClose={onClose}
      footer={
        <>
          <div className="flex gap-2">
            <button type="button" onClick={onEdit} className={`${primaryButtonClass} flex-1`}>{tr("Edit")}</button>
            <button type="button" onClick={onDuplicate} className={`${secondaryButtonClass} h-12 flex-1`}>{tr("Duplicate")}</button>
          </div>
          <button
            type="button"
            onClick={() => {
              if (confirm(tr("Delete this {type} of {date}? Positions and cash are recalculated without it.", { type: tr(t.type), date: formatDate(t.date) }))) onDelete();
            }}
            className="h-11 rounded-xl text-[15px] font-semibold text-ui-late hover:bg-ui-late-soft"
          >{tr("Delete transaction…")}</button>
        </>
      }
    >
      <div className="flex flex-col gap-4 pt-1">
        <div className="flex flex-col gap-1">
          <span className="text-[15px] font-semibold text-ui-ink-soft">{t.asset_name ?? (t.type === "Transfer" ? tr("Cash transfer") : tr("Cash"))}</span>
          <span className="font-display text-4xl font-bold leading-none tracking-[-0.02em] tabular-nums">{formatEur(t.total_eur)}</span>
        </div>
        <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-3">
          {fields.map(([label, value]) => (
            <div key={label} className="flex min-w-0 flex-col gap-0.5">
              <dt className="text-[13px] text-ui-muted">{label}</dt>
              <dd className="m-0 truncate text-[15px] font-semibold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        {t.notes && <p className="m-0 whitespace-pre-line rounded-xl bg-ui-tile px-3 py-2.5 text-sm">{t.notes}</p>}
        {onOpenPosition && (
          <button
            type="button"
            onClick={onOpenPosition}
            className="flex h-12 items-center justify-between rounded-xl bg-ui-tile px-3.5 text-[15px] font-semibold text-ui-ink hover:bg-ui-line/60"
          >{t.ticker ? tr("Open position: {ticker}", { ticker: t.ticker }) : tr("Open position")}

            <span aria-hidden>›</span>
          </button>
        )}
      </div>
    </Sheet>
  );
}
