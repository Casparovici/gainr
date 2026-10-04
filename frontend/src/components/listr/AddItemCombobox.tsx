import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrItem } from "../../api/listrTypes";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

/** Search-as-you-type over the grocery catalog, with an inline "+ Nieuw product" path when
 * what you typed isn't in the catalog yet -- the one place "add new products myself if they
 * don't exist" actually happens, reused from both a list and a recipe. */
export default function AddItemCombobox({
  onSelect,
  placeholder = "Product zoeken of toevoegen…",
  initialQuery = "",
}: {
  onSelect: (item: ListrItem) => void;
  placeholder?: string;
  /** Pre-fills the search, e.g. with an imported ingredient's name, so "+ toevoegen" is one tap. */
  initialQuery?: string;
}) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState(initialQuery);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newCategoryId, setNewCategoryId] = useState("");
  const [newUnit, setNewUnit] = useState("stuks");
  const [highlighted, setHighlighted] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: items } = useQuery({ queryKey: ["listr-items"], queryFn: () => listrApi.listItems() });
  const { data: categories } = useQuery({
    queryKey: ["listr-categories"],
    queryFn: () => listrApi.listCategories(),
  });

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  const createMutation = useMutation({
    mutationFn: () =>
      listrApi.createItem({ name: query.trim(), category_id: Number(newCategoryId), default_unit: newUnit }),
    onSuccess: (item) => {
      queryClient.invalidateQueries({ queryKey: ["listr-items"] });
      onSelect(item);
      reset();
    },
  });

  function reset() {
    setQuery("");
    setOpen(false);
    setCreating(false);
    setNewCategoryId("");
    setNewUnit("stuks");
  }

  const trimmed = query.trim();
  const filtered = trimmed
    ? (items ?? []).filter((i) => i.name.toLowerCase().includes(trimmed.toLowerCase())).slice(0, 8)
    : (items ?? []).slice(0, 8);
  const exactMatch = (items ?? []).some((i) => i.name.toLowerCase() === trimmed.toLowerCase());
  const showCreateOption = Boolean(trimmed && !exactMatch);
  const optionCount = filtered.length + (showCreateOption ? 1 : 0);

  function startCreating() {
    setCreating(true);
    setNewCategoryId(categories?.[0] ? String(categories[0].id) : "");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (creating) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setHighlighted((h) => Math.min(h + 1, optionCount - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (!open || optionCount === 0) return;
      e.preventDefault();
      if (highlighted < filtered.length) {
        onSelect(filtered[highlighted]);
        reset();
      } else {
        startCreating();
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setCreating(false);
          setHighlighted(0);
        }}
        onFocus={() => {
          setOpen(true);
          setHighlighted(0);
        }}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className={`${inputClass} w-full`}
      />

      {open && !creating && (
        <div className="absolute left-0 top-full z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          {filtered.length === 0 && !trimmed && (
            <div className="px-2 py-1.5 text-sm text-slate-400">Typ om te zoeken…</div>
          )}
          {filtered.map((item, i) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onSelect(item);
                reset();
              }}
              onMouseEnter={() => setHighlighted(i)}
              className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm ${
                i === highlighted ? "bg-slate-100" : "hover:bg-slate-50"
              }`}
            >
              <span className="text-slate-900">{item.name}</span>
              <span className="text-xs text-slate-400">{item.category_name}</span>
            </button>
          ))}
          {showCreateOption && (
            <button
              type="button"
              onClick={startCreating}
              onMouseEnter={() => setHighlighted(filtered.length)}
              className={`mt-1 w-full rounded-md border-t border-slate-100 px-2 py-1.5 text-left text-sm text-blue-700 ${
                filtered.length === highlighted ? "bg-slate-50" : "hover:bg-slate-50"
              }`}
            >
              + "{trimmed}" toevoegen aan producten
            </button>
          )}
        </div>
      )}

      {creating && (
        <div className="absolute left-0 top-full z-20 mt-1 w-72 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
          <div className="text-sm font-medium text-slate-900">Nieuw product: "{trimmed}"</div>
          <label className="mt-2 flex flex-col gap-1 text-xs">
            <span className="font-medium uppercase tracking-wide text-slate-500">Categorie</span>
            <select
              value={newCategoryId}
              onChange={(e) => setNewCategoryId(e.target.value)}
              className={inputClass}
            >
              {(categories ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-2 flex flex-col gap-1 text-xs">
            <span className="font-medium uppercase tracking-wide text-slate-500">Eenheid</span>
            <input value={newUnit} onChange={(e) => setNewUnit(e.target.value)} className={inputClass} placeholder="stuks, kg, liter…" />
          </label>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreating(false)}
              className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              Terug
            </button>
            <button
              type="button"
              disabled={!newCategoryId || !newUnit.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
              className="rounded-md bg-slate-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {createMutation.isPending ? "Bezig…" : "Toevoegen"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
