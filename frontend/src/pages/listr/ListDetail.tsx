import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingCart, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import type { ListrItem, ListrListItem } from "../../api/listrTypes";
import AddItemCombobox from "../../components/listr/AddItemCombobox";
import PicnicProductPicker from "../../components/listr/PicnicProductPicker";
import PicnicThumb from "../../components/listr/PicnicThumb";
import { IconChevronLeft, ModuleTopRow, PageTitle, secondaryButtonClass } from "../../components/ui/kit";
import { usePicnicConnect } from "../../hooks/usePicnicConnect";
import { categoryIcon } from "../../utils/categoryIcons";
import { decimalInputToApi, formatEur, formatQuantity, toNumber } from "../../utils/format";

function groupByCategory(items: ListrListItem[]): { categoryId: number; categoryName: string; items: ListrListItem[] }[] {
  const groups = new Map<number, { categoryId: number; categoryName: string; items: ListrListItem[] }>();
  for (const item of items) {
    if (!groups.has(item.category_id)) {
      groups.set(item.category_id, { categoryId: item.category_id, categoryName: item.category_name, items: [] });
    }
    groups.get(item.category_id)!.items.push(item);
  }
  return [...groups.values()].sort((a, b) => a.categoryName.localeCompare(b.categoryName));
}

export default function ListrListDetail() {
  const { id } = useParams<{ id: string }>();
  const listId = Number(id);
  const queryClient = useQueryClient();
  const [pushSummary, setPushSummary] = useState<string | null>(null);

  const { data: list, isLoading } = useQuery({
    queryKey: ["listr-list", listId],
    queryFn: () => listrApi.getList(listId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["listr-list", listId] });
    queryClient.invalidateQueries({ queryKey: ["listr-lists"] });
  };

  const addItemMutation = useMutation({
    mutationFn: (item: ListrItem) => listrApi.addListItem(listId, { grocery_item_id: item.id }),
    onSuccess: invalidate,
  });
  const toggleCheckedMutation = useMutation({
    mutationFn: ({ itemId, is_checked }: { itemId: number; is_checked: boolean }) =>
      listrApi.updateListItem(listId, itemId, { is_checked }),
    onSuccess: invalidate,
  });
  const updateQuantityMutation = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: string }) =>
      listrApi.updateListItem(listId, itemId, { quantity }),
    onSuccess: invalidate,
  });
  const deleteItemMutation = useMutation({
    mutationFn: (itemId: number) => listrApi.deleteListItem(listId, itemId),
    onSuccess: invalidate,
  });
  const clearCheckedMutation = useMutation({
    mutationFn: () => listrApi.clearChecked(listId),
    onSuccess: invalidate,
  });

  // -- picnic (see docs/adr/0011-listr-picnic-integration.md) -------------------------------
  const pushToPicnicMutation = useMutation({
    mutationFn: () => listrApi.pushListToPicnic(listId),
    onSuccess: (result) => {
      const parts: string[] = [];
      if (result.pushed.length) parts.push(`${result.pushed.length} toegevoegd aan je Picnic-winkelwagen`);
      if (result.unmapped_item_ids.length) {
        parts.push(
          `${result.unmapped_item_ids.length} nog te koppelen — klik het winkelwagen-icoon naast een product hieronder`,
        );
      }
      setPushSummary(parts.length ? parts.join(" · ") : "Niets om toe te voegen.");
    },
  });
  const picnic = usePicnicConnect(() => pushToPicnicMutation.mutate());

  function handlePushToPicnic() {
    setPushSummary(null);
    picnic.connect();
  }

  if (isLoading || !list) {
    return <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>;
  }

  const groups = groupByCategory(list.items);
  // What "Push naar Picnic" would put in the cart -- one of each unchecked, priced product, the
  // same count-1 rule the push itself follows -- so this is a floor, not a quote.
  const pricedOpen = list.items.filter((i) => !i.is_checked && i.picnic_price !== null);
  const picnicEstimate = pricedOpen.reduce((sum, i) => sum + (toNumber(i.picnic_price) ?? 0), 0);

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow
        left={
          <Link to="/listr" aria-label="Terug naar lijsten" className={`${secondaryButtonClass} pl-2 pr-3 no-underline`}>
            <IconChevronLeft size={20} />
            Lijsten
          </Link>
        }
      >
        {picnic.status?.configured && (
          <div className="relative">
            <button
              onClick={handlePushToPicnic}
              disabled={picnic.isConnecting || pushToPicnicMutation.isPending}
              className={secondaryButtonClass}
            >
              <ShoppingCart className="h-4 w-4" strokeWidth={2} />
              {picnic.isConnecting || pushToPicnicMutation.isPending ? (
                "Bezig…"
              ) : (
                <>
                  <span className="sm:hidden">Picnic</span>
                  <span className="hidden sm:inline">Push naar Picnic</span>
                </>
              )}
            </button>
            {picnic.awaiting2FA && (
              <div className="absolute right-0 top-full z-20 mt-1 w-64 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
                <div className="text-sm font-medium text-slate-900">Code van Picnic invoeren</div>
                <p className="mt-0.5 text-xs text-slate-400">Picnic heeft je zojuist een sms gestuurd.</p>
                <input
                  autoFocus
                  inputMode="numeric"
                  value={picnic.code}
                  onChange={(e) => picnic.setCode(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && picnic.code.trim()) picnic.verify();
                  }}
                  placeholder="123456"
                  className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
                {picnic.verifyError && (
                  <p className="mt-1 text-xs text-red-600">Code niet geaccepteerd, probeer opnieuw.</p>
                )}
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    onClick={picnic.cancel}
                    className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Annuleren
                  </button>
                  <button
                    disabled={!picnic.code.trim() || picnic.isVerifying}
                    onClick={picnic.verify}
                    className="rounded-md bg-slate-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                  >
                    Bevestigen
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </ModuleTopRow>

      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <PageTitle
            size="md"
            subtitle={
              list.items.length === 0
                ? "Nog leeg"
                : `${list.checked_count} / ${list.items.length} afgevinkt` +
                  (pricedOpen.length > 0 ? ` · ≈ ${formatEur(picnicEstimate)} bij Picnic` : "")
            }
          >
            {list.name}
          </PageTitle>
        </div>
        {list.checked_count > 0 && (
          <button onClick={() => clearCheckedMutation.mutate()} className={`${secondaryButtonClass} shrink-0`}>
            <Trash2 className="h-4 w-4" strokeWidth={2} />
            <span className="sm:hidden">Afgevinkt ({list.checked_count})</span>
            <span className="hidden sm:inline">Afgevinkte verwijderen ({list.checked_count})</span>
          </button>
        )}
      </div>

      {pushSummary && (
        <p className="m-0 flex flex-wrap items-center gap-x-2 text-sm text-ui-ink-soft">
          {pushSummary}
          <Link to="/listr/winkelwagen" className="font-semibold text-ui-brand-strong">
            Naar winkelwagen ›
          </Link>
        </p>
      )}
      {(picnic.connectError || pushToPicnicMutation.isError) && !picnic.awaiting2FA && (
        <p className="text-sm text-red-600">Verbinden met Picnic is mislukt. Probeer het later opnieuw.</p>
      )}

      <div className="w-full max-w-sm">
        <AddItemCombobox onSelect={(item) => addItemMutation.mutate(item)} />
      </div>

      {list.items.length === 0 ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted">
          Nog geen producten op deze lijst — zoek hierboven om iets toe te voegen.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {groups.map((group) => {
            const Icon = categoryIcon(group.categoryName);
            return (
              <div key={group.categoryId} className="overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
                <div className="flex items-center gap-2 border-b border-ui-border px-4 py-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ui-brand-soft text-ui-brand-strong">
                    <Icon className="h-4 w-4" strokeWidth={2} />
                  </span>
                  <span className="text-[15px] font-semibold text-ui-ink">{group.categoryName}</span>
                  <span className="ml-auto text-sm text-ui-muted">
                    {group.items.filter((i) => i.is_checked).length} / {group.items.length}
                  </span>
                </div>
                <ul>
                  {group.items.map((item) => (
                    <li
                      key={item.id}
                      // On a phone the name gets the first line to itself and the controls wrap
                      // underneath; from sm up it's all one row.
                      className="flex min-h-[48px] flex-wrap items-center gap-x-3 gap-y-1 border-b border-ui-border px-4 py-1.5 last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={item.is_checked}
                        onChange={(e) =>
                          toggleCheckedMutation.mutate({ itemId: item.id, is_checked: e.target.checked })
                        }
                        aria-label={item.grocery_item_name}
                        className="h-5 w-5 shrink-0 accent-ui-brand"
                      />
                      {item.picnic_image_url && <PicnicThumb url={item.picnic_image_url} size={36} />}
                      <span className="flex min-w-0 flex-1 basis-[calc(100%-6rem)] flex-col sm:basis-0">
                        <span className={`truncate text-[15px] ${item.is_checked ? "text-ui-muted line-through" : "text-ui-ink"}`}>
                          {item.grocery_item_name}
                        </span>
                        {item.picnic_price !== null && (
                          <span className="truncate text-xs text-ui-muted" title={item.picnic_product_name ?? undefined}>
                            {formatEur(item.picnic_price)}
                            {item.picnic_unit_quantity && ` / ${item.picnic_unit_quantity}`}
                          </span>
                        )}
                      </span>
                      <div className="ml-auto flex shrink-0 items-center gap-3">
                        <input
                          inputMode="decimal"
                          defaultValue={formatQuantity(item.quantity)}
                          onBlur={(e) => {
                            const parsed = decimalInputToApi(e.target.value);
                            if (parsed !== null && Number(parsed) > 0 && parsed !== item.quantity) {
                              updateQuantityMutation.mutate({ itemId: item.id, quantity: parsed });
                            } else {
                              e.target.value = formatQuantity(item.quantity);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") e.currentTarget.blur();
                          }}
                          className="h-9 w-14 rounded-[10px] border border-ui-line bg-ui-surface px-2 text-right text-sm tabular-nums text-ui-ink focus:border-ui-brand focus:outline-none focus:ring-1 focus:ring-ui-brand"
                        />
                        <span className="w-12 shrink-0 text-xs text-ui-muted">{item.unit}</span>
                        {picnic.status?.connected && (
                          <PicnicProductPicker
                            groceryItemId={item.grocery_item_id}
                            itemName={item.grocery_item_name}
                            mappedName={item.picnic_product_name}
                          />
                        )}
                        <button
                          type="button"
                          onClick={() => deleteItemMutation.mutate(item.id)}
                          className="-mr-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ui-faint hover:text-ui-late"
                          title="Verwijderen"
                          aria-label="Verwijderen"
                        >
                          <Trash2 className="h-4 w-4" strokeWidth={2} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
