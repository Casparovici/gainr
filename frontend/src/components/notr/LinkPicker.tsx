import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../api/client";
import { gardnrApi } from "../../api/gardnrClient";
import { listrApi } from "../../api/listrClient";
import type { NotrNote } from "../../api/notrTypes";
import { t } from "../../i18n";
import { QueryError } from "../ui/QueryError";
import { inputClass } from "../ui/kit";
import { RemovableLinkChips, type LinkKind, type NoteLink } from "./LinkChips";

export interface LinkIds {
  asset_ids: number[];
  plant_ids: number[];
  recipe_ids: number[];
}

const MAX_PER_KIND = 6;

const KIND_HEADINGS: Record<LinkKind, () => string> = {
  asset: () => t("Positions"),
  plant: () => t("Plants"),
  recipe: () => t("Recipes"),
};

type Option = NoteLink & { hint?: string };

/** What a note is about: the positions, plants and recipes it's linked to, as removable chips, and
 * one search box that finds more of any of the three. Positions come from gainr's assets (the cash
 * row is no position), plants from gardnr and recipes from listr -- each adapter is behind its own
 * client, so this never knows where they live. `known` are the links the note already has, so a
 * chip keeps its name even when the option lists don't carry it (an archived plant, a sold
 * position). */
export default function LinkPicker({
  value,
  known,
  onChange,
}: {
  value: LinkIds;
  known?: Pick<NotrNote, "assets" | "plants" | "recipes">;
  onChange: (value: LinkIds) => void;
}) {
  const assetsQuery = useQuery({ queryKey: ["assets"], queryFn: api.listAssets, staleTime: Infinity });
  const plantsQuery = useQuery({ queryKey: ["gardnr-plants", false], queryFn: () => gardnrApi.listPlants(false) });
  const recipesQuery = useQuery({ queryKey: ["listr-recipes"], queryFn: () => listrApi.listRecipes() });

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const options = useMemo<Option[]>(
    () => [
      ...(assetsQuery.data ?? [])
        .filter((a) => a.ticker !== "CASH")
        .map((a): Option => ({ kind: "asset", id: a.id, label: a.ticker, hint: a.name })),
      ...(plantsQuery.data ?? []).map((p): Option => ({ kind: "plant", id: p.id, label: p.name, hint: p.area_name })),
      ...(recipesQuery.data ?? []).map((r): Option => ({ kind: "recipe", id: r.id, label: r.title })),
    ],
    [assetsQuery.data, plantsQuery.data, recipesQuery.data],
  );

  const idsOf = (kind: LinkKind): number[] =>
    kind === "asset" ? value.asset_ids : kind === "plant" ? value.plant_ids : value.recipe_ids;

  const chosen = useMemo<NoteLink[]>(() => {
    const nameOf = (kind: LinkKind, id: number): string => {
      const fromNote =
        kind === "asset"
          ? known?.assets.find((a) => a.id === id)?.ticker
          : kind === "plant"
            ? known?.plants.find((p) => p.id === id)?.name
            : known?.recipes.find((r) => r.id === id)?.title;
      return fromNote ?? options.find((o) => o.kind === kind && o.id === id)?.label ?? "…";
    };
    return [
      ...value.asset_ids.map((id): NoteLink => ({ kind: "asset", id, label: nameOf("asset", id) })),
      ...value.plant_ids.map((id): NoteLink => ({ kind: "plant", id, label: nameOf("plant", id) })),
      ...value.recipe_ids.map((id): NoteLink => ({ kind: "recipe", id, label: nameOf("recipe", id) })),
    ];
  }, [value, known, options]);

  const needle = query.trim().toLowerCase();
  const matches = options.filter(
    (o) =>
      !idsOf(o.kind).includes(o.id) &&
      (!needle || o.label.toLowerCase().includes(needle) || (o.hint ?? "").toLowerCase().includes(needle)),
  );
  const kinds: LinkKind[] = ["asset", "plant", "recipe"];

  const loading = assetsQuery.isPending || plantsQuery.isPending || recipesQuery.isPending;
  const failed = assetsQuery.isError || plantsQuery.isError || recipesQuery.isError;

  function add(option: Option) {
    const key = option.kind === "asset" ? "asset_ids" : option.kind === "plant" ? "plant_ids" : "recipe_ids";
    onChange({ ...value, [key]: [...value[key], option.id] });
    setQuery("");
    setOpen(false);
  }

  function remove(link: NoteLink) {
    const key = link.kind === "asset" ? "asset_ids" : link.kind === "plant" ? "plant_ids" : "recipe_ids";
    onChange({ ...value, [key]: value[key].filter((id) => id !== link.id) });
  }

  return (
    <div className="flex flex-col gap-2" ref={box}>
      <RemovableLinkChips links={chosen} onRemove={remove} />
      <div className="relative">
        <input
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder={t("Link a position, plant or recipe…")}
          aria-label={t("Link a position, plant or recipe")}
          className={inputClass}
        />
        {open && (
          <div className="absolute left-0 top-full z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-xl border border-ui-line bg-ui-surface p-1 shadow-lg">
            {loading && <p className="m-0 px-3 py-2 text-sm text-ui-muted">{t("Loading…")}</p>}
            {!loading && matches.length === 0 && !failed && (
              <p className="m-0 px-3 py-2 text-sm text-ui-muted">{t("Nothing to link.")}</p>
            )}
            {kinds.map((kind) => {
              const rows = matches.filter((o) => o.kind === kind).slice(0, MAX_PER_KIND);
              if (rows.length === 0) return null;
              return (
                <div key={kind} role="group" aria-label={KIND_HEADINGS[kind]()}>
                  <p className="m-0 px-3 pb-0.5 pt-2 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">
                    {KIND_HEADINGS[kind]()}
                  </p>
                  {rows.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      onClick={() => add(o)}
                      className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-3 text-left text-[15px] hover:bg-ui-tile"
                    >
                      <span className="truncate text-ui-ink">{o.label}</span>
                      {o.hint && <span className="shrink-0 truncate text-xs text-ui-muted">{o.hint}</span>}
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
      {failed && (
        <QueryError
          className="text-sm"
          message={t("Couldn't load everything you can link.")}
          onRetry={() => {
            void assetsQuery.refetch();
            void plantsQuery.refetch();
            void recipesQuery.refetch();
          }}
        />
      )}
    </div>
  );
}
