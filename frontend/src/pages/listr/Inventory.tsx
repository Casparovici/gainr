import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus, X } from "lucide-react";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrInventoryStatus, ListrItem } from "../../api/listrTypes";
import AddItemCombobox from "../../components/listr/AddItemCombobox";
import InventoryAddToListDialog from "../../components/listr/InventoryAddToListDialog";
import { IconAlert, IconChevronRight, ModuleTopRow, PageTitle } from "../../components/ui/kit";
import { categoryIcon } from "../../utils/categoryIcons";

const STATUS_LABELS: Record<ListrInventoryStatus, string> = {
  in_stock: "Op voorraad",
  low: "Bijna op",
  out: "Op",
};

const STATUS_DOT_CLASS: Record<ListrInventoryStatus, string> = {
  in_stock: "bg-emerald-500",
  low: "bg-ui-today-dot",
  out: "bg-ui-late",
};

/** Mirrors the server's _compute_inventory_status (backend/app/routers/listr.py) exactly, so the
 * optimistic count/minimum update below can also update the status dot instead of leaving it
 * showing the pre-click colour until the round-trip to the server settles. */
function computeInventoryStatus(count: number, minimum: number): ListrInventoryStatus {
  if (count === 0) return "out";
  if (count < minimum) return "low";
  return "in_stock";
}

/** A +/- pair around a number -- every adjustment is a server round-trip via `onAdjust(delta)`,
 * never a locally-typed draft value. Count and minimum both use this: typing into a text field
 * and committing on blur turned out to be the fragile part (see docs/adr/0015's third addendum
 * -- a blur-timing race could drop an in-progress edit before it was ever sent), while the
 * count's own +/- buttons, which never held draft state, had been reliably persisting the whole
 * time. */
function Stepper({
  value,
  onAdjust,
  decrementLabel,
  incrementLabel,
}: {
  value: number;
  onAdjust: (delta: number) => void;
  decrementLabel: string;
  incrementLabel: string;
}) {
  return (
    <span className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => onAdjust(-1)}
        disabled={value === 0}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-ui-line bg-ui-surface text-ui-ink-soft hover:bg-ui-tile disabled:opacity-30"
        title={decrementLabel}
        aria-label={decrementLabel}
      >
        <Minus className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
      <span className="w-5 text-center text-[15px] font-semibold tabular-nums text-ui-ink">{value}</span>
      <button
        type="button"
        onClick={() => onAdjust(1)}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-ui-line bg-ui-surface text-ui-ink-soft hover:bg-ui-tile"
        title={incrementLabel}
        aria-label={incrementLabel}
      >
        <Plus className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
    </span>
  );
}

function InventoryItemRow({
  item,
  onAdjustCount,
  onAdjustMinimum,
  onUntrack,
}: {
  item: ListrItem;
  onAdjustCount: (delta: number) => void;
  onAdjustMinimum: (delta: number) => void;
  onUntrack: () => void;
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 py-2 pl-4 pr-2 text-[15px] text-ui-ink">
      <span className="min-w-0 flex-1 basis-32 truncate">{item.name}</span>
      <span className="ml-auto flex shrink-0 items-center gap-2.5">
        <Stepper value={item.inventory_count} onAdjust={onAdjustCount} decrementLabel="Een minder" incrementLabel="Een meer" />
        <span className="flex items-center gap-1 text-xs text-ui-muted" title="Daaronder springt de status naar Bijna op">
          min
          <Stepper
            value={item.inventory_minimum}
            onAdjust={onAdjustMinimum}
            decrementLabel="Minimum een lager"
            incrementLabel="Minimum een hoger"
          />
        </span>
        <span
          className={`h-3.5 w-3.5 shrink-0 rounded-full ${item.inventory_status ? STATUS_DOT_CLASS[item.inventory_status] : "bg-ui-border"}`}
          title={item.inventory_status ? STATUS_LABELS[item.inventory_status] : undefined}
        />
        <button
          type="button"
          onClick={onUntrack}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-ui-faint hover:text-ui-ink"
          title="Niet meer bijhouden"
          aria-label="Niet meer bijhouden"
        >
          <X className="h-4 w-4" strokeWidth={2} />
        </button>
      </span>
    </li>
  );
}

function groupByCategory(items: ListrItem[]): { categoryId: number; categoryName: string; items: ListrItem[] }[] {
  const groups = new Map<number, { categoryId: number; categoryName: string; items: ListrItem[] }>();
  for (const item of items) {
    if (!groups.has(item.category_id)) {
      groups.set(item.category_id, { categoryId: item.category_id, categoryName: item.category_name ?? "", items: [] });
    }
    groups.get(item.category_id)!.items.push(item);
  }
  return [...groups.values()].sort((a, b) => a.categoryName.localeCompare(b.categoryName));
}

function RestockBanner({ count, anyOut, onClick }: { count: number; anyOut: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-3 rounded-2xl px-4 py-3.5 text-left ${anyOut ? "bg-ui-late-soft text-ui-late" : "bg-ui-today-soft text-ui-today"}`}
    >
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white ${anyOut ? "bg-ui-late" : "bg-ui-today-dot"}`}>
        <IconAlert size={18} strokeWidth={3} />
      </span>
      <span className="flex min-w-0 flex-grow flex-col gap-px">
        <span className="text-[15px] font-bold">
          {count} product{count === 1 ? "" : "en"} moet{count === 1 ? "" : "en"} aangevuld worden
        </span>
        <span className={`text-[13px] ${anyOut ? "text-ui-late-ink" : "text-ui-today"}`}>Zet ze op een boodschappenlijst</span>
      </span>
      <span className="flex shrink-0 items-center gap-0.5 text-sm font-semibold">
        Lijst
        <IconChevronRight size={16} />
      </span>
    </button>
  );
}

export default function ListrInventory() {
  const queryClient = useQueryClient();
  const [showAddToList, setShowAddToList] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data: items, isLoading } = useQuery({
    queryKey: ["listr-inventory"],
    queryFn: () => listrApi.listInventory(),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["listr-inventory"] });

  const setTrackingMutation = useMutation({
    mutationFn: ({ id, tracked }: { id: number; tracked: boolean }) => listrApi.setItemInventoryTracking(id, tracked),
    onSuccess: invalidate,
  });

  const adjustCountMutation = useMutation({
    mutationFn: ({ id, delta }: { id: number; delta: number }) => listrApi.adjustInventoryCount(id, delta),
    // Optimistic, so a quick run of taps feels instant instead of round-tripping per click --
    // clamped at 0 client-side too, matching the server's own floor.
    onMutate: async ({ id, delta }) => {
      await queryClient.cancelQueries({ queryKey: ["listr-inventory"] });
      const previous = queryClient.getQueryData<ListrItem[]>(["listr-inventory"]);
      queryClient.setQueryData<ListrItem[]>(["listr-inventory"], (old) =>
        old?.map((i) => {
          if (i.id !== id) return i;
          const inventory_count = Math.max(0, i.inventory_count + delta);
          const inventory_status = i.inventory_status ? computeInventoryStatus(inventory_count, i.inventory_minimum) : i.inventory_status;
          return { ...i, inventory_count, inventory_status };
        }),
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(["listr-inventory"], context.previous);
    },
    onSettled: invalidate,
  });

  const adjustMinimumMutation = useMutation({
    mutationFn: ({ id, delta }: { id: number; delta: number }) => listrApi.adjustInventoryMinimum(id, delta),
    onMutate: async ({ id, delta }) => {
      await queryClient.cancelQueries({ queryKey: ["listr-inventory"] });
      const previous = queryClient.getQueryData<ListrItem[]>(["listr-inventory"]);
      queryClient.setQueryData<ListrItem[]>(["listr-inventory"], (old) =>
        old?.map((i) => {
          if (i.id !== id) return i;
          const inventory_minimum = Math.max(0, i.inventory_minimum + delta);
          const inventory_status = i.inventory_status ? computeInventoryStatus(i.inventory_count, inventory_minimum) : i.inventory_status;
          return { ...i, inventory_minimum, inventory_status };
        }),
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(["listr-inventory"], context.previous);
    },
    onSettled: invalidate,
  });

  const addToListMutation = useMutation({
    mutationFn: (input: { listId: number | null; newListName: string | null; itemIds: number[] }) =>
      listrApi.addInventoryToList({
        item_ids: input.itemIds,
        list_id: input.listId ?? undefined,
        new_list_name: input.newListName ?? undefined,
      }),
    onSuccess: (list) => {
      setShowAddToList(false);
      setFeedback(`Toegevoegd aan "${list.name}".`);
      queryClient.invalidateQueries({ queryKey: ["listr-lists"] });
    },
  });

  const needsRestocking = (items ?? []).filter((i) => i.inventory_status === "low" || i.inventory_status === "out");
  const groups = groupByCategory(items ?? []);

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow />
      <PageTitle subtitle={items && items.length > 0 ? `${items.length} producten bijgehouden` : undefined}>Voorraad</PageTitle>

      <div className="w-full sm:max-w-sm">
        <AddItemCombobox
          placeholder="Product bijhouden…"
          onSelect={(item) => setTrackingMutation.mutate({ id: item.id, tracked: true })}
        />
      </div>

      {/* Like gardnr's due banner: red when something has run out, amber when it's only running
          low. The whole banner opens the add-to-list dialog. */}
      {needsRestocking.length > 0 && (
        <RestockBanner
          count={needsRestocking.length}
          anyOut={needsRestocking.some((i) => i.inventory_status === "out")}
          onClick={() => setShowAddToList(true)}
        />
      )}
      {feedback && <div className="text-sm font-medium text-ui-ink-soft">{feedback}</div>}

      {isLoading ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>
      ) : groups.length === 0 ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">
          Nog geen producten bijgehouden. Zoek hierboven een product om het toe te voegen aan je voorraad.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {groups.map((group) => {
            const Icon = categoryIcon(group.categoryName);
            return (
              <div key={group.categoryId} className="overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
                <div className="flex items-center gap-2 border-b border-ui-border px-4 py-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ui-brand-soft text-ui-brand-strong">
                    <Icon className="h-4 w-4" strokeWidth={2} />
                  </span>
                  <span className="text-[15px] font-semibold text-ui-ink">{group.categoryName}</span>
                  <span className="ml-auto text-sm text-ui-muted">{group.items.length}</span>
                </div>
                <ul className="divide-y divide-ui-border">
                  {group.items.map((item) => (
                    <InventoryItemRow
                      key={item.id}
                      item={item}
                      onAdjustCount={(delta) => adjustCountMutation.mutate({ id: item.id, delta })}
                      onAdjustMinimum={(delta) => adjustMinimumMutation.mutate({ id: item.id, delta })}
                      onUntrack={() => setTrackingMutation.mutate({ id: item.id, tracked: false })}
                    />
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}

      {showAddToList && (
        <InventoryAddToListDialog
          items={needsRestocking}
          isSubmitting={addToListMutation.isPending}
          onCancel={() => setShowAddToList(false)}
          onSubmit={(input) => addToListMutation.mutate(input)}
        />
      )}
    </div>
  );
}
