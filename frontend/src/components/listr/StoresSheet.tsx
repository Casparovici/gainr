import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrCategory, ListrStore } from "../../api/listrTypes";
import { QueryError } from "../ui/QueryError";
import { dangerButtonClass, iconButtonClass, inputClass, primaryButtonClass, secondaryButtonClass } from "../ui/kit";
import Sheet from "../ui/Sheet";
import { t } from "../../i18n";

/** Which order the sheet is arranging: a supermarket, or the standard order every list without a
 * store follows. */
type Target = { kind: "default" } | { kind: "store"; storeId: number };

/** The supermarkets, and the order their aisles come in (docs/adr/0052). A list set to a store
 * shows its categories in that order, so it follows the walk through the shop. Opened from a
 * list's store picker. Every change is saved as it's made, like the list's own steppers. */
export default function StoresSheet({ onClose }: { onClose: () => void }) {
  const [target, setTarget] = useState<Target | null>(null);
  const queryClient = useQueryClient();

  const storesQuery = useQuery({ queryKey: ["listr-stores"], queryFn: () => listrApi.listStores() });
  const categoriesQuery = useQuery({ queryKey: ["listr-categories"], queryFn: () => listrApi.listCategories() });

  // The stores, the lists (which show a store's order) and the categories (the standard order)
  // all move together when one is arranged.
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["listr-stores"] });
    queryClient.invalidateQueries({ queryKey: ["listr-categories"] });
    queryClient.invalidateQueries({ queryKey: ["listr-list"] });
    queryClient.invalidateQueries({ queryKey: ["listr-lists"] });
  };

  const stores = storesQuery.data;
  const categories = categoriesQuery.data;
  const store = target?.kind === "store" ? stores?.find((s) => s.id === target.storeId) : undefined;
  const title = !target ? t("Winkels") : target.kind === "default" ? t("Standaard volgorde") : (store?.name ?? t("Winkels"));

  return (
    <Sheet title={title} onClose={onClose}>
      <div className="flex flex-col gap-4 pb-4 pt-1">
        {target !== null && (
          <button type="button" onClick={() => setTarget(null)} className={`${secondaryButtonClass} self-start pl-2 pr-3`}>
            {t("‹ Winkels")}
          </button>
        )}
        {storesQuery.isError || categoriesQuery.isError ? (
          <QueryError
            message={t("Kon de winkels niet laden.")}
            retryLabel={t("Opnieuw proberen")}
            onRetry={() => {
              void storesQuery.refetch();
              void categoriesQuery.refetch();
            }}
          />
        ) : !stores || !categories ? (
          <div className="h-32 animate-pulse rounded-xl bg-ui-tile" />
        ) : target === null ? (
          <Overview stores={stores} onOpen={setTarget} onChanged={refresh} />
        ) : target.kind === "default" ? (
          <OrderEditor
            key="default"
            categories={categories}
            order={categories.map((c) => c.id)}
            hint={t("De volgorde van een lijst zonder winkel. Zet de categorieën zoals je meestal door de winkel loopt.")}
            save={(ids) => listrApi.reorderCategories(ids).then(() => undefined)}
            onSaved={refresh}
          />
        ) : store ? (
          <StoreEditor key={store.id} store={store} categories={categories} onChanged={refresh} onBack={() => setTarget(null)} />
        ) : (
          // The store went away (deleted elsewhere): the back button above leads out.
          <p className="m-0 text-sm text-ui-muted">{t("Deze winkel bestaat niet meer.")}</p>
        )}
      </div>
    </Sheet>
  );
}

function Overview({
  stores,
  onOpen,
  onChanged,
}: {
  stores: ListrStore[];
  onOpen: (target: Target) => void;
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [copyFrom, setCopyFrom] = useState("");
  const createMutation = useMutation({
    mutationFn: () => listrApi.createStore({ name: name.trim(), copy_order_from_id: copyFrom ? Number(copyFrom) : null }),
    onSuccess: (created) => {
      setName("");
      setCopyFrom("");
      onChanged();
      onOpen({ kind: "store", storeId: created.id });
    },
  });

  return (
    <>
      <p className="m-0 text-sm text-ui-muted">
        {t("Elke winkel heeft zijn eigen looproute. Kies bij een lijst een winkel, en de lijst volgt de volgorde van de gangpaden.")}
      </p>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        <li>
          <RowButton label={t("Standaard volgorde")} detail={t("voor lijsten zonder winkel")} onClick={() => onOpen({ kind: "default" })} />
        </li>
        {stores.map((s) => (
          <li key={s.id}>
            <RowButton
              label={s.name}
              detail={s.category_ids.length ? t("{n} gangen geordend", { n: s.category_ids.length }) : t("nog niet geordend")}
              onClick={() => onOpen({ kind: "store", storeId: s.id })}
            />
          </li>
        ))}
      </ul>
      {stores.length === 0 && <p className="m-0 text-sm text-ui-muted">{t("Nog geen winkels. Voeg er een toe, bijvoorbeeld je supermarkt.")}</p>}

      <form
        className="flex flex-col gap-2 border-t border-ui-line pt-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) createMutation.mutate();
        }}
      >
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">
          {t("Nieuwe winkel")}
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("Naam, bijvoorbeeld Jumbo")} maxLength={120} className={inputClass} />
        </label>
        {stores.length > 0 && (
          <label className="flex flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">
            {t("Begin met de volgorde van")}
            <select value={copyFrom} onChange={(e) => setCopyFrom(e.target.value)} className={inputClass}>
              <option value="">{t("Standaard volgorde")}</option>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {createMutation.isError && (
          <p role="alert" className="m-0 text-sm text-ui-late">
            {createMutation.error instanceof Error && createMutation.error.message.startsWith("409")
              ? t("Er is al een winkel met die naam.")
              : t("Kon de winkel niet toevoegen.")}
          </p>
        )}
        <button type="submit" disabled={!name.trim() || createMutation.isPending} className={primaryButtonClass}>
          {t("Winkel toevoegen")}
        </button>
      </form>
    </>
  );
}

function RowButton({ label, detail, onClick }: { label: string; detail: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[52px] w-full items-center gap-3 rounded-xl border border-ui-line bg-ui-surface px-3.5 text-left hover:bg-ui-tile"
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-[15px] font-semibold text-ui-ink">{label}</span>
        <span className="truncate text-xs text-ui-muted">{detail}</span>
      </span>
      <span aria-hidden className="text-ui-faint">›</span>
    </button>
  );
}

function StoreEditor({
  store,
  categories,
  onChanged,
  onBack,
}: {
  store: ListrStore;
  categories: ListrCategory[];
  onChanged: () => void;
  onBack: () => void;
}) {
  const [name, setName] = useState(store.name);
  const renameMutation = useMutation({
    mutationFn: () => listrApi.renameStore(store.id, name.trim()),
    onSuccess: onChanged,
  });
  const deleteMutation = useMutation({
    mutationFn: () => listrApi.deleteStore(store.id),
    onSuccess: () => {
      onChanged();
      onBack();
    },
  });
  const renamed = name.trim() !== "" && name.trim() !== store.name;

  return (
    <>
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (renamed) renameMutation.mutate();
        }}
      >
        <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">
          {t("Naam")}
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className={inputClass} />
        </label>
        {renamed && (
          <button type="submit" disabled={renameMutation.isPending} className={secondaryButtonClass}>
            {t("Opslaan")}
          </button>
        )}
      </form>
      {renameMutation.isError && (
        <p role="alert" className="m-0 text-sm text-ui-late">
          {renameMutation.error instanceof Error && renameMutation.error.message.startsWith("409")
            ? t("Er is al een winkel met die naam.")
            : t("Kon de naam niet opslaan.")}
        </p>
      )}

      <OrderEditor
        categories={categories}
        order={store.category_order}
        hint={t("Zet de categorieën in de volgorde waarin je door deze winkel loopt. Een lijst voor deze winkel volgt die.")}
        save={(ids) => listrApi.setStoreOrder(store.id, ids).then(() => undefined)}
        onSaved={onChanged}
      />

      <button
        type="button"
        className={`${dangerButtonClass} self-start`}
        onClick={() => {
          if (confirm(t("{name} verwijderen? Lijsten die deze winkel volgen gaan terug naar de standaard volgorde.", { name: store.name }))) {
            deleteMutation.mutate();
          }
        }}
      >
        {t("Winkel verwijderen…")}
      </button>
    </>
  );
}

/** The categories in an order, each with arrows to move it a place -- native buttons rather than
 * dragging, which is awkward on a phone. A move is saved at once. */
function OrderEditor({
  categories,
  order,
  hint,
  save,
  onSaved,
}: {
  categories: ListrCategory[];
  order: number[];
  hint: string;
  save: (categoryIds: number[]) => Promise<void>;
  onSaved: () => void;
}) {
  const byId = new Map(categories.map((c) => [c.id, c]));
  // Archived categories aren't arranged here; they keep their place behind the scenes.
  const initial = order.filter((id) => byId.has(id));
  const [ids, setIds] = useState(initial);
  const saveMutation = useMutation({ mutationFn: (next: number[]) => save(next), onSuccess: onSaved });

  const move = (index: number, delta: number) => {
    const next = [...ids];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setIds(next);
    saveMutation.mutate(next);
  };

  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-sm text-ui-muted">{hint}</p>
      {ids.length === 0 ? (
        <p className="m-0 text-sm text-ui-muted">{t("Er zijn nog geen categorieën.")}</p>
      ) : (
        <ol className="m-0 flex list-none flex-col gap-1.5 p-0">
          {ids.map((id, index) => (
            <li key={id} className="flex items-center gap-2 rounded-xl border border-ui-line bg-ui-surface py-1 pl-3 pr-1">
              <span aria-hidden className="w-5 shrink-0 text-sm tabular-nums text-ui-muted">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-[15px] text-ui-ink">{byId.get(id)?.name}</span>
              <button
                type="button"
                className={iconButtonClass}
                disabled={index === 0}
                onClick={() => move(index, -1)}
                aria-label={t("{name} eerder zetten", { name: byId.get(id)?.name ?? "" })}
              >
                <ArrowUp size={18} aria-hidden />
              </button>
              <button
                type="button"
                className={iconButtonClass}
                disabled={index === ids.length - 1}
                onClick={() => move(index, 1)}
                aria-label={t("{name} later zetten", { name: byId.get(id)?.name ?? "" })}
              >
                <ArrowDown size={18} aria-hidden />
              </button>
            </li>
          ))}
        </ol>
      )}
      {saveMutation.isError && (
        <p role="alert" className="m-0 text-sm text-ui-late">
          {t("Kon de volgorde niet opslaan.")}
        </p>
      )}
    </div>
  );
}
