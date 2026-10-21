import type { ListrLeftoverLocation } from "../../api/listrTypes";
import { inputClass } from "../ui/kit";
import { msg, t } from "../../i18n";

export interface LeftoverDraft {
  meals: number;
  servings: string;
  location: ListrLeftoverLocation;
  useBy: string;
}

export const EMPTY_LEFTOVER_DRAFT: LeftoverDraft = { meals: 2, servings: "4", location: "freezer", useBy: "" };

const LOCATIONS: { value: ListrLeftoverLocation; label: string }[] = [
  { value: "freezer", label: msg("Vriezer") },
  { value: "fridge", label: msg("Koelkast") },
];

/** The part of a leftover that isn't its name: how many meals, for how many people, where it is
 * and until when it keeps. Shared by the Voorraad dialog and the "restjes bewaren?" panel in the
 * weekplanner's day editor. A blank use-by date is filled in by the server per location. */
export default function LeftoverFields({ value, onChange }: { value: LeftoverDraft; onChange: (next: LeftoverDraft) => void }) {
  const set = <K extends keyof LeftoverDraft>(key: K, v: LeftoverDraft[K]) => onChange({ ...value, [key]: v });
  const label = "text-xs font-medium uppercase tracking-wide text-ui-muted";
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        {LOCATIONS.map((l) => (
          <button
            key={l.value}
            type="button"
            onClick={() => set("location", l.value)}
            aria-pressed={value.location === l.value}
            className={`h-11 flex-1 rounded-xl border text-[15px] font-semibold ${
              value.location === l.value ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong" : "border-ui-line text-ui-ink-soft"
            }`}
          >
            {t(l.label)}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1">
          <span className={label}>{t("Maaltijden")}</span>
          <input
            type="number"
            min={1}
            value={value.meals}
            onChange={(e) => set("meals", Math.max(1, Number(e.target.value) || 1))}
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className={label}>{t("Personen per maaltijd")}</span>
          <input
            type="number"
            min={1}
            value={value.servings}
            onChange={(e) => set("servings", e.target.value)}
            placeholder={t("optioneel")}
            className={inputClass}
          />
        </label>
      </div>
      <label className="flex flex-col gap-1">
        <span className={label}>{t("Houdbaar tot")}</span>
        <input type="date" value={value.useBy} onChange={(e) => set("useBy", e.target.value)} className={inputClass} />
        <span className="text-xs text-ui-muted">{value.location === "fridge" ? t("Leeg laten = 3 dagen vanaf vandaag") : t("Leeg laten = 3 maanden vanaf vandaag")}</span>
      </label>
    </div>
  );
}

export function draftToInput(name: string, recipeId: number | null, draft: LeftoverDraft) {
  const servings = Number(draft.servings);
  return {
    name: name.trim(),
    recipe_id: recipeId,
    meals: draft.meals,
    servings_per_meal: servings >= 1 ? servings : null,
    location: draft.location,
    use_by: draft.useBy || null,
  };
}
