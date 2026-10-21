import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ShoppingCart, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import type { ListrItem, ListrListItem } from "../../api/listrTypes";
import AddItemCombobox from "../../components/listr/AddItemCombobox";
import ListItemSheet from "../../components/listr/ListItemSheet";
import StoresSheet from "../../components/listr/StoresSheet";
import PicnicThumb from "../../components/listr/PicnicThumb";
import { IconChevronLeft, ModuleTopRow, PageTitle, inputClass, primaryButtonClass, secondaryButtonClass } from "../../components/ui/kit";
import { useCollapsedGroups } from "../../hooks/useCollapsedGroups";
import { usePicnicConnect } from "../../hooks/usePicnicConnect";
import { categoryIcon } from "../../utils/categoryIcons";
import { formatEur, formatQuantity, toNumber } from "../../utils/format";
import { t } from "../../i18n";

/** The store picker's last option, which opens the stores sheet instead of choosing a store. */
const MANAGE_STORES = "manage";

/** The list's lines grouped by category, the groups in `categoryOrder` -- the store's aisles, then
 * the rest (the server says which; docs/adr/0052). A category it doesn't know comes last, by name. */
export function groupByCategory(
  items: ListrListItem[],
  categoryOrder: number[],
): { categoryId: number; categoryName: string; items: ListrListItem[] }[] {
  const groups = new Map<number, { categoryId: number; categoryName: string; items: ListrListItem[] }>();
  for (const item of items) {
    if (!groups.has(item.category_id)) {
      groups.set(item.category_id, { categoryId: item.category_id, categoryName: item.category_name, items: [] });
    }
    groups.get(item.category_id)!.items.push(item);
  }
  const place = (id: number) => {
    const at = categoryOrder.indexOf(id);
    return at === -1 ? Number.MAX_SAFE_INTEGER : at;
  };
  return [...groups.values()].sort((a, b) => place(a.categoryId) - place(b.categoryId) || a.categoryName.localeCompare(b.categoryName));
}

export default function ListrListDetail() {
  const { id } = useParams<{ id: string }>();
  const listId = Number(id);
  const queryClient = useQueryClient();
  const [pushSummary, setPushSummary] = useState<string | null>(null);
  // By id, so the open sheet follows the list as it refetches after a change.
  const [openItemId, setOpenItemId] = useState<number | null>(null);
  const [storesOpen, setStoresOpen] = useState(false);
  const folded = useCollapsedGroups(`listr-collapsed-${listId}`);

  const { data: list, isLoading } = useQuery({
    queryKey: ["listr-list", listId],
    queryFn: () => listrApi.getList(listId),
  });

  const storesQuery = useQuery({ queryKey: ["listr-stores"], queryFn: () => listrApi.listStores() });
  const stores = storesQuery.data ?? [];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["listr-list", listId] });
    queryClient.invalidateQueries({ queryKey: ["listr-lists"] });
  };

  const storeMutation = useMutation({
    mutationFn: (storeId: number | null) => listrApi.updateList(listId, { store_id: storeId }),
    onSuccess: invalidate,
  });
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
      if (result.pushed.length) parts.push(t("{count} toegevoegd aan je Picnic-winkelwagen", { count: result.pushed.length }));
      if (result.unmapped_item_ids.length) {
        parts.push(
          t("{count} nog te koppelen — klik het winkelwagen-icoon naast een product hieronder", {
            count: result.unmapped_item_ids.length,
          }),
        );
      }
      setPushSummary(parts.length ? parts.join(" · ") : t("Niets om toe te voegen."));
    },
  });
  const picnic = usePicnicConnect(() => pushToPicnicMutation.mutate());

  function handlePushToPicnic() {
    setPushSummary(null);
    picnic.connect();
  }

  if (isLoading || !list) {
    return <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">{t("Laden…")}</div>;
  }

  const groups = groupByCategory(list.items, list.category_order);
  const groupIds = groups.map((g) => g.categoryId);
  const openItem = list.items.find((i) => i.id === openItemId) ?? null;
  // What "Push naar Picnic" would put in the cart -- one of each unchecked, priced product, the
  // same count-1 rule the push itself follows -- so this is a floor, not a quote.
  const pricedOpen = list.items.filter((i) => !i.is_checked && i.picnic_price !== null);
  const picnicEstimate = pricedOpen.reduce((sum, i) => sum + (toNumber(i.picnic_price) ?? 0), 0);

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow
        left={
          <Link to="/listr" aria-label={t("Terug naar lijsten")} className={`${secondaryButtonClass} pl-2 pr-3 no-underline`}>
            <IconChevronLeft size={20} />{t("Lijsten")}</Link>
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
                t("Bezig…")
              ) : (
                <>
                  <span className="sm:hidden">Picnic</span>
                  <span className="hidden sm:inline">{t("Push naar Picnic")}</span>
                </>
              )}
            </button>
            {picnic.awaiting2FA && (
              <div className="absolute right-0 top-full z-20 mt-1 w-64 rounded-xl border border-ui-line bg-ui-surface p-3 shadow-lg">
                <div className="text-sm font-semibold text-ui-ink">{t("Code van Picnic invoeren")}</div>
                <p className="mt-0.5 text-xs text-ui-muted">{t("Picnic heeft je zojuist een sms gestuurd.")}</p>
                <input
                  autoFocus
                  inputMode="numeric"
                  value={picnic.code}
                  onChange={(e) => picnic.setCode(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && picnic.code.trim()) picnic.verify();
                  }}
                  placeholder="123456"
                  className={`${inputClass} mt-2`}
                />
                {picnic.verifyError && (
                  <p role="alert" className="mt-1 text-xs text-ui-late">{t("Code niet geaccepteerd, probeer opnieuw.")}</p>
                )}
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    onClick={picnic.cancel}
                    className={secondaryButtonClass}
                  >{t("Annuleren")}</button>
                  <button
                    disabled={!picnic.code.trim() || picnic.isVerifying}
                    onClick={picnic.verify}
                    className={primaryButtonClass}
                  >{t("Bevestigen")}</button>
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
                ? t("Nog leeg")
                : t("{checked} / {total} afgevinkt", { checked: list.checked_count, total: list.items.length }) +
                  (pricedOpen.length > 0 ? ` · ${t("≈ {amount} bij Picnic", { amount: formatEur(picnicEstimate) })}` : "")
            }
          >
            {list.name}
          </PageTitle>
        </div>
        {list.checked_count > 0 && (
          <button onClick={() => clearCheckedMutation.mutate()} className={`${secondaryButtonClass} shrink-0`}>
            <Trash2 className="h-4 w-4" strokeWidth={2} />
            <span className="sm:hidden">{t("Afgevinkt ({checkedcount})", { checkedcount: list.checked_count })}</span>
            <span className="hidden sm:inline">{t("Afgevinkte verwijderen ({checkedcount})", { checkedcount: list.checked_count })}</span>
          </button>
        )}
      </div>

      <div className="flex items-center gap-2">
        <label htmlFor="list-store" className="shrink-0 text-sm font-semibold text-ui-ink-soft">{t("Winkel")}</label>
        <select
          id="list-store"
          value={list.store_id ?? ""}
          onChange={(e) => {
            if (e.target.value === MANAGE_STORES) setStoresOpen(true);
            else storeMutation.mutate(e.target.value === "" ? null : Number(e.target.value));
          }}
          className="h-11 min-w-0 max-w-xs flex-1 rounded-xl border border-ui-line bg-ui-surface px-3 text-base text-ui-ink"
        >
          <option value="">{t("Standaard volgorde")}</option>
          {stores.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
          <option value={MANAGE_STORES}>{t("Winkels beheren…")}</option>
        </select>
        {storeMutation.isError && <span role="alert" className="text-sm text-ui-late">{t("Kon de winkel niet wijzigen.")}</span>}
      </div>

      {pushSummary && (
        <p className="m-0 flex flex-wrap items-center gap-x-2 text-sm text-ui-ink-soft">
          {pushSummary}
          <Link to="/listr/winkelwagen" className="font-semibold text-ui-brand-strong">{t("Naar winkelwagen ›")}</Link>
        </p>
      )}
      {(picnic.connectError || pushToPicnicMutation.isError) && !picnic.awaiting2FA && (
        <p role="alert" className="text-sm text-ui-late">{t("Verbinden met Picnic is mislukt. Probeer het later opnieuw.")}</p>
      )}

      <div className="w-full max-w-sm">
        <AddItemCombobox onSelect={(item) => addItemMutation.mutate(item)} />
      </div>

      {list.items.length === 0 ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted">{t("Nog geen producten op deze lijst — zoek hierboven om iets toe te voegen.")}</div>
      ) : (
        <div className="flex flex-col gap-4">
          {groups.length > 1 && (
            <button
              type="button"
              onClick={() => folded.setAll(groupIds, !folded.allCollapsed(groupIds))}
              className="-mb-2 flex h-9 items-center self-end rounded-lg px-2 text-sm font-semibold text-ui-brand-strong hover:bg-ui-tile"
            >
              {folded.allCollapsed(groupIds) ? t("Alles uitklappen") : t("Alles inklappen")}
            </button>
          )}
          {groups.map((group) => {
            const Icon = categoryIcon(group.categoryName);
            const isOpen = folded.isOpen(group.categoryId);
            const checkedCount = group.items.filter((i) => i.is_checked).length;
            const done = checkedCount === group.items.length;
            return (
              <div key={group.categoryId} className="overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
                <button
                  type="button"
                  onClick={() => folded.toggle(group.categoryId)}
                  aria-expanded={isOpen}
                  aria-controls={`listr-group-${group.categoryId}`}
                  className={`flex min-h-[52px] w-full items-center gap-2 px-4 py-3 text-left hover:bg-ui-tile ${isOpen ? "border-b border-ui-border" : ""}`}
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ui-brand-soft text-ui-brand-strong">
                    <Icon className="h-4 w-4" strokeWidth={2} />
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[15px] font-semibold text-ui-ink">{group.categoryName}</span>
                  <span className={`flex shrink-0 items-center gap-1 text-sm tabular-nums ${done ? "text-ui-brand-strong" : "text-ui-muted"}`}>
                    {done && <Check className="h-4 w-4" strokeWidth={2.5} aria-hidden />}
                    {checkedCount} / {group.items.length}
                  </span>
                  <ChevronDown
                    aria-hidden
                    className={`h-5 w-5 shrink-0 text-ui-faint transition-transform ${isOpen ? "" : "-rotate-90"}`}
                    strokeWidth={2}
                  />
                </button>
                <ul id={`listr-group-${group.categoryId}`} hidden={!isOpen}>
                  {group.items.map((item) => (
                    // One line per item, to tick off while shopping; how much, the Picnic product
                    // and removing it are in the item's sheet, a tap on its amount away.
                    <li key={item.id} className="flex items-center gap-3 border-b border-ui-border px-4 last:border-0">
                      {/* The checkbox, the thumbnail and the name are one tap target: ticking off
                          while shopping shouldn't need a 20 px aim. */}
                      <label className="flex min-h-[52px] min-w-0 flex-1 cursor-pointer items-center gap-3">
                        <input
                          type="checkbox"
                          checked={item.is_checked}
                          onChange={(e) =>
                            toggleCheckedMutation.mutate({ itemId: item.id, is_checked: e.target.checked })
                          }
                          aria-label={item.grocery_item_name}
                          className="h-5 w-5 shrink-0 accent-ui-brand"
                        />
                        {item.picnic_image_url && <PicnicThumb url={item.picnic_image_url} size={32} />}
                        <span className="flex min-w-0 flex-1 flex-col py-1.5">
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
                      </label>
                      <button
                        type="button"
                        onClick={() => setOpenItemId(item.id)}
                        aria-label={t("{name}: {quantity} {unit}, aanpassen", { name: item.grocery_item_name, quantity: formatQuantity(item.quantity), unit: item.unit ?? "" })}
                        className="-mr-2 flex h-11 shrink-0 items-center gap-1 rounded-xl px-2.5 text-sm tabular-nums text-ui-ink-soft hover:bg-ui-tile"
                      >
                        {formatQuantity(item.quantity)} {item.unit}
                        <span aria-hidden className="text-ui-faint">›</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}

      {storesOpen && <StoresSheet onClose={() => setStoresOpen(false)} />}

      {openItem && (
        <ListItemSheet
          key={openItem.id}
          item={openItem}
          picnicConnected={Boolean(picnic.status?.connected)}
          onQuantity={(quantity) => updateQuantityMutation.mutate({ itemId: openItem.id, quantity })}
          onDelete={() => deleteItemMutation.mutate(openItem.id)}
          onClose={() => setOpenItemId(null)}
        />
      )}
    </div>
  );
}
