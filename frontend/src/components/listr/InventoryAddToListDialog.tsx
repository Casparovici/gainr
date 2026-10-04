import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrItem } from "../../api/listrTypes";
import ModalOverlay from "../ModalOverlay";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const NEW_LIST = "__new__";

/** Bulk sibling of AddToListDialog for the "aan te vullen" (low/out) inventory items -- every
 * item goes on at quantity 1 of its own default unit, same as inventory/add-to-list does; the
 * checkboxes let the reader drop specific items from an otherwise all-checked bulk add. */
export default function InventoryAddToListDialog({
  items,
  isSubmitting,
  onCancel,
  onSubmit,
}: {
  items: ListrItem[];
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (input: { listId: number | null; newListName: string | null; itemIds: number[] }) => void;
}) {
  const { data: lists } = useQuery({ queryKey: ["listr-lists", false], queryFn: () => listrApi.listLists() });
  const [selected, setSelected] = useState<Set<number>>(new Set(items.map((i) => i.id)));
  const [listChoice, setListChoice] = useState<string>(NEW_LIST);
  const [newListName, setNewListName] = useState("Aanvullen");

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    onSubmit({
      listId: listChoice === NEW_LIST ? null : Number(listChoice),
      newListName: listChoice === NEW_LIST ? newListName.trim() : null,
      itemIds: [...selected],
    });
  }

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-md rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">Toevoegen aan boodschappenlijst</h2>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex max-h-64 flex-col gap-1 overflow-y-auto rounded-md border border-slate-200 p-2">
          {items.map((item) => (
            <label key={item.id} className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-slate-50">
              <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggle(item.id)} />
              <span className="flex-1 text-slate-900">{item.name}</span>
              <span className="tabular-nums text-slate-400">1 {item.default_unit}</span>
            </label>
          ))}
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Lijst</span>
          <select value={listChoice} onChange={(e) => setListChoice(e.target.value)} className={inputClass}>
            <option value={NEW_LIST}>+ Nieuwe lijst…</option>
            {(lists ?? []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        {listChoice === NEW_LIST && (
          <input
            required
            value={newListName}
            onChange={(e) => setNewListName(e.target.value)}
            placeholder="Naam van de nieuwe lijst"
            className={inputClass}
          />
        )}

        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Annuleren
          </button>
          <button
            type="submit"
            disabled={isSubmitting || selected.size === 0}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isSubmitting ? "Bezig…" : `Toevoegen (${selected.size})`}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}
