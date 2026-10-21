import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrRecipe } from "../../api/listrTypes";
import { QueryError } from "../ui/QueryError";
import { t } from "../../i18n";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

/** Search-as-you-type over recipes by title -- the weekplanner's day-editor uses this to pick
 * which recipe a date gets assigned to. A trimmed sibling of AddItemCombobox's dropdown half:
 * a meal always references an existing recipe (or none), so there's no inline-create path. */
export default function RecipePickerCombobox({
  onSelect,
  placeholder = t("Recept zoeken…"),
}: {
  onSelect: (recipe: ListrRecipe) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: recipes, isError, refetch } = useQuery({ queryKey: ["listr-recipes"], queryFn: () => listrApi.listRecipes() });

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  const trimmed = query.trim();
  const filtered = trimmed
    ? (recipes ?? []).filter((r) => r.title.toLowerCase().includes(trimmed.toLowerCase())).slice(0, 8)
    : (recipes ?? []).slice(0, 8);

  function selectRecipe(recipe: ListrRecipe) {
    onSelect(recipe);
    setQuery("");
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (!open || filtered.length === 0) return;
      e.preventDefault();
      selectRecipe(filtered[highlighted]);
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

      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          {isError ? (
            <QueryError className="px-2 py-1.5 text-sm" message={t("Recepten laden mislukt.")} onRetry={() => refetch()} retryLabel={t("Opnieuw")} />
          ) : (
            filtered.length === 0 && (
              <div className="px-2 py-1.5 text-sm text-slate-400">
                {trimmed ? t("Geen recepten gevonden.") : t("Typ om te zoeken…")}
              </div>
            )
          )}
          {filtered.map((recipe, i) => (
            <button
              key={recipe.id}
              type="button"
              onClick={() => selectRecipe(recipe)}
              onMouseEnter={() => setHighlighted(i)}
              className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm ${
                i === highlighted ? "bg-slate-100" : "hover:bg-slate-50"
              }`}
            >
              <span className="text-slate-900">{recipe.title}</span>
              {recipe.servings && <span className="text-xs text-slate-400">{recipe.servings}{" "}{t("pers.")}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
