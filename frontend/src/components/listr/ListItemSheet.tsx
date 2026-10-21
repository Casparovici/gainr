import { Minus, Plus } from "lucide-react";
import { useState } from "react";

import type { ListrListItem } from "../../api/listrTypes";
import { decimalInputToApi, formatEur, formatQuantity, toNumber } from "../../utils/format";
import { dangerButtonClass } from "../ui/kit";
import Sheet from "../ui/Sheet";
import PicnicProductPicker from "./PicnicProductPicker";
import PicnicThumb from "./PicnicThumb";
import { t } from "../../i18n";

/** One item on a shopping list, opened from its row: how much, which Picnic product, and
 * removing it. Every change is saved as it's made (a +/- or a typed amount on Enter or leaving
 * the field), like the inventory's steppers -- there's no draft to lose. */
export default function ListItemSheet({
  item,
  picnicConnected,
  onQuantity,
  onDelete,
  onClose,
}: {
  item: ListrListItem;
  picnicConnected: boolean;
  onQuantity: (quantity: string) => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const current = toNumber(item.quantity) ?? 1;
  const [typed, setTyped] = useState(formatQuantity(item.quantity));

  const commit = (value: string) => {
    const parsed = decimalInputToApi(value);
    if (parsed !== null && Number(parsed) > 0 && parsed !== item.quantity) {
      onQuantity(parsed);
    } else {
      setTyped(formatQuantity(item.quantity));
    }
  };
  const step = (delta: number) => {
    const next = Math.round((current + delta) * 1000) / 1000;
    if (next <= 0) return;
    setTyped(formatQuantity(String(next)));
    onQuantity(String(next));
  };

  return (
    <Sheet
      title={item.grocery_item_name}
      onClose={onClose}
      footer={
        <button
          type="button"
          onClick={() => {
            onDelete();
            onClose();
          }}
          className={`${dangerButtonClass} justify-center`}
        >{t("Van de lijst halen")}</button>
      }
    >
      <div className="flex flex-col gap-5 pt-2">
        {item.picnic_image_url && (
          <div className="flex items-center gap-3">
            <PicnicThumb url={item.picnic_image_url} size={56} />
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-[15px] font-semibold">{item.picnic_product_name}</span>
              {item.picnic_price !== null && (
                <span className="text-sm text-ui-muted">
                  {formatEur(item.picnic_price)}
                  {item.picnic_unit_quantity && ` / ${item.picnic_unit_quantity}`}
                </span>
              )}
            </span>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold text-ui-ink-soft">{t("Hoeveel")}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => step(-1)}
              disabled={current <= 1}
              aria-label={t("Een minder")}
              className="flex h-11 w-11 items-center justify-center rounded-xl border border-ui-line bg-ui-surface text-ui-ink hover:bg-ui-tile disabled:opacity-30"
            >
              <Minus className="h-4 w-4" strokeWidth={2.2} />
            </button>
            <label className="sr-only" htmlFor={`qty-${item.id}`}>{t("Hoeveelheid")}</label>
            <input
              id={`qty-${item.id}`}
              inputMode="decimal"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onBlur={(e) => commit(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur();
              }}
              className="h-11 w-20 rounded-xl border border-ui-line bg-ui-surface px-3 text-center text-base font-semibold tabular-nums text-ui-ink focus:border-ui-brand focus:outline-none"
            />
            <button
              type="button"
              onClick={() => step(1)}
              aria-label={t("Een meer")}
              className="flex h-11 w-11 items-center justify-center rounded-xl border border-ui-line bg-ui-surface text-ui-ink hover:bg-ui-tile"
            >
              <Plus className="h-4 w-4" strokeWidth={2.2} />
            </button>
            <span className="text-[15px] text-ui-muted">{item.unit}</span>
          </div>
        </div>

        {picnicConnected && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold text-ui-ink-soft">{t("Picnic-product")}</span>
            <PicnicProductPicker groceryItemId={item.grocery_item_id} itemName={item.grocery_item_name} mappedName={item.picnic_product_name} />
          </div>
        )}
      </div>
    </Sheet>
  );
}
