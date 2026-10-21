import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrExercise } from "../../api/trainrTypes";
import ModalOverlay from "../ModalOverlay";
import { inputClass, secondaryButtonClass } from "../ui/kit";
import ExerciseDemo from "./ExerciseDemo";
import { t } from "../../i18n";

const SEARCH_DEBOUNCE_MS = 250;

/** Links a how-to demo to an exercise (ADR 0040): the current one playing on top, and a search of
 * the catalogue underneath, opened on the exercise's own name so the usual case is one tap. The
 * catalogue is English, hence the hint. */
export default function ExerciseDemoPicker({
  exercise,
  isSaving,
  error,
  onPick,
  onClose,
}: {
  exercise: TrainrExercise;
  isSaving: boolean;
  error: string | null;
  onPick: (demoId: string | null) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState(exercise.name);
  const [debounced, setDebounced] = useState(exercise.name);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(query.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [query]);

  const results = useQuery({
    queryKey: ["trainr-exercise-demos", debounced],
    queryFn: () => trainrApi.searchExerciseDemos(debounced),
    enabled: debounced.length > 0,
    staleTime: Infinity,
  });
  const options = (results.data ?? []).filter((d) => d.id !== exercise.demo_id);

  return (
    <ModalOverlay onClose={onClose} cardClassName="flex max-h-[90vh] w-full max-w-lg flex-col rounded-lg bg-white shadow-lg">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-5 py-4">
        <h2 className="truncate text-base font-semibold text-slate-900">{t("Voorbeeld · {name}", { name: exercise.name })}</h2>
        <button type="button" onClick={onClose} className="text-sm font-medium text-slate-500 hover:text-slate-800">{t("Sluiten")}</button>
      </div>

      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-5 py-4">
        {exercise.demo ? (
          <div className="flex flex-col gap-2">
            <ExerciseDemo key={exercise.demo.id} demo={exercise.demo} />
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm text-ui-ink-soft">{exercise.demo.name}</span>
              <button type="button" onClick={() => onPick(null)} disabled={isSaving} className={secondaryButtonClass}>{t("Ontkoppelen")}</button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-ui-muted">{t("Nog geen voorbeeld. Kies er hieronder een; de training laat het zien bij deze oefening.")}</p>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("Zoek in het Engels, bv. hammer curl")}
          aria-label={t("Zoek een voorbeeld")}
          className={inputClass}
        />

        {debounced.length === 0 ? (
          <p className="text-sm text-ui-muted">{t("Typ een oefening om voorbeelden te zoeken.")}</p>
        ) : results.isLoading ? (
          <p className="text-sm text-ui-muted">{t("Zoeken…")}</p>
        ) : results.isError ? (
          <p className="text-sm text-ui-muted">{t("Zoeken is mislukt.")}{" "}
            <button type="button" onClick={() => results.refetch()} className="font-medium text-slate-900 underline">{t("Opnieuw proberen")}</button>
          </p>
        ) : options.length === 0 ? (
          <p className="text-sm text-ui-muted">{t("Niets gevonden voor “{debounced}” — probeer minder of andere (Engelse) woorden, bv. “curl”.", { debounced: debounced })}</p>
        ) : (
          <ul className="m-0 flex list-none flex-col p-0" aria-label={t("Voorbeelden")}>
            {options.map((d) => (
              <li key={d.id} className="border-b border-ui-border last:border-0">
                <button
                  type="button"
                  onClick={() => onPick(d.id)}
                  disabled={isSaving}
                  className="flex w-full items-center gap-3 py-2 text-left disabled:opacity-50"
                >
                  <img src={d.image_urls[0]} alt="" loading="lazy" className="h-12 w-[4.5rem] shrink-0 rounded-md border border-ui-border bg-white object-contain" />
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-[15px] font-semibold text-ui-ink">{d.name}</span>
                    {d.equipment && <span className="text-xs text-ui-muted">{d.equipment}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </ModalOverlay>
  );
}
