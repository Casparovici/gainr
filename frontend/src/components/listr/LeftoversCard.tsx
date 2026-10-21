import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrLeftover, ListrLeftoverInput } from "../../api/listrTypes";
import ModalOverlay from "../ModalOverlay";
import { IconPlus, StatusChip, inputClass, primaryButtonClass, secondaryButtonClass } from "../ui/kit";
import LeftoverFields, { EMPTY_LEFTOVER_DRAFT, draftToInput, type LeftoverDraft } from "./LeftoverFields";
import RecipePickerCombobox from "./RecipePickerCombobox";
import Stepper from "./Stepper";
import { dateLocale, msg, t, tp } from "../../i18n";

const LOCATION_LABEL = { freezer: msg("Vriezer"), fridge: msg("Koelkast") };

function daysUntil(iso: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((new Date(iso + "T00:00:00").getTime() - today.getTime()) / 86_400_000);
}

function formatUseBy(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short" });
}

function UseByChip({ useBy }: { useBy: string }) {
  const days = daysUntil(useBy);
  if (days < 0) return <StatusChip kind="late">{t("Verlopen")}{" "}{formatUseBy(useBy)}</StatusChip>;
  if (days <= 3) return <StatusChip kind="today">{days === 0 ? t("Vandaag op") : tp(days, "Nog {n} dag", "Nog {n} dagen")}</StatusChip>;
  return <span className="text-xs text-ui-muted">{t("tot")}{" "}{formatUseBy(useBy)}</span>;
}

function NewLeftoverDialog({ isSubmitting, onCancel, onSubmit }: {
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (input: ReturnType<typeof draftToInput>) => void;
}) {
  const [name, setName] = useState("");
  const [recipeId, setRecipeId] = useState<number | null>(null);
  const [draft, setDraft] = useState<LeftoverDraft>(EMPTY_LEFTOVER_DRAFT);

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">{t("Restjes bewaren")}</h2>
      <form
        className="mt-4 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onSubmit(draftToInput(name, recipeId, draft));
        }}
      >
        <RecipePickerCombobox
          placeholder={t("Recept kiezen (optioneel)…")}
          onSelect={(recipe) => {
            setRecipeId(recipe.id);
            setName(recipe.title);
          }}
        />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("Naam, bv. Bolognese")}
          aria-label={t("Naam")}
          className={inputClass}
        />
        <LeftoverFields value={draft} onChange={setDraft} />
        <div className="mt-1 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className={secondaryButtonClass}>{t("Annuleren")}</button>
          <button type="submit" disabled={isSubmitting || !name.trim()} className={primaryButtonClass}>
            {isSubmitting ? t("Bezig…") : t("Opslaan")}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}

function LeftoverRow({ leftover, onAdjust, onDelete }: {
  leftover: ListrLeftover;
  onAdjust: (delta: number) => void;
  onDelete: () => void;
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 py-2 pl-4 pr-2 text-[15px] text-ui-ink">
      <span className="flex min-w-0 flex-1 basis-40 flex-col">
        <span className="truncate">{leftover.name}</span>
        <span className="flex flex-wrap items-center gap-x-2 text-xs text-ui-muted">
          {t(LOCATION_LABEL[leftover.location])}
          {leftover.servings_per_meal ? ` · ${t("{servings} pers.", { servings: leftover.servings_per_meal })}` : ""}
          <UseByChip useBy={leftover.use_by} />
        </span>
      </span>
      <span className="ml-auto flex shrink-0 items-center gap-2.5">
        <Stepper value={leftover.meals} onAdjust={onAdjust} decrementLabel={t("Een maaltijd minder")} incrementLabel={t("Een maaltijd meer")} />
        <button
          type="button"
          onClick={onDelete}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-ui-faint hover:text-ui-ink"
          title={t("Verwijderen")}
          aria-label={t("{name} verwijderen", { name: leftover.name })}
        >
          <X className="h-4 w-4" strokeWidth={2} />
        </button>
      </span>
    </li>
  );
}

/** Voorraad's "Restjes" card: cooked meals kept for later, soonest use-by first. A batch that
 * reaches 0 meals drops off the list on its own (see docs/adr/0036-listr-leftovers.md). */
export default function LeftoversCard() {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);

  const { data: leftovers, isLoading, isError } = useQuery({
    queryKey: ["listr-leftovers"],
    queryFn: () => listrApi.listLeftovers(),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["listr-leftovers"] });

  const createMutation = useMutation({
    mutationFn: (input: ListrLeftoverInput) => listrApi.createLeftover(input),
    onSuccess: () => {
      setAdding(false);
      invalidate();
    },
  });
  const adjustMutation = useMutation({
    mutationFn: ({ id, delta }: { id: number; delta: number }) => listrApi.adjustLeftoverMeals(id, delta),
    onSettled: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => listrApi.deleteLeftover(id),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["listr-meal-plan"] });
    },
  });

  return (
    <div className="overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
      <div className="flex items-center gap-2 border-b border-ui-border px-4 py-3">
        <span className="text-[15px] font-semibold text-ui-ink">{t("Restjes")}</span>
        {leftovers && leftovers.length > 0 && <span className="text-sm text-ui-muted">{leftovers.length}</span>}
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="ml-auto flex h-8 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-ui-brand-strong hover:bg-ui-tile"
        >
          <IconPlus size={14} />{" "}{t("Bewaren")}</button>
      </div>
      {isLoading ? (
        <div className="px-4 py-4 text-center text-ui-muted">{t("Laden…")}</div>
      ) : isError ? (
        <div className="px-4 py-4 text-center text-ui-late">{t("Restjes laden mislukt.")}</div>
      ) : !leftovers || leftovers.length === 0 ? (
        <div className="px-4 py-4 text-center text-ui-muted">{t("Geen restjes. Bewaar wat je overhoudt na het koken.")}</div>
      ) : (
        <ul className="divide-y divide-ui-border">
          {leftovers.map((l) => (
            <LeftoverRow
              key={l.id}
              leftover={l}
              onAdjust={(delta) => adjustMutation.mutate({ id: l.id, delta })}
              onDelete={() => deleteMutation.mutate(l.id)}
            />
          ))}
        </ul>
      )}
      {adding && (
        <NewLeftoverDialog
          isSubmitting={createMutation.isPending}
          onCancel={() => setAdding(false)}
          onSubmit={(input) => createMutation.mutate(input)}
        />
      )}
    </div>
  );
}
