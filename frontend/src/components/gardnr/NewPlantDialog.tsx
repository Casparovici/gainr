import { useState } from "react";

import { GARDEN_PLANT_TYPE_LABELS, GARDEN_PLANT_TYPES, type GardenArea, type GardenPlantType } from "../../api/gardnrTypes";
import ModalOverlay from "../ModalOverlay";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

export interface NewPlantInput {
  name: string;
  type: GardenPlantType;
  species: string;
  areaId: number | null;
}

/** The new-plant form, shared by the map (where the tapped spot already decides the garden) and
 * Planten (where it's added without a map position, so it asks which garden it belongs to). */
export default function NewPlantDialog({
  areas,
  hint,
  onCancel,
  onSubmit,
  isSubmitting,
  isError,
}: {
  /** Pass the gardens to choose from when the plant isn't being placed on a specific map. */
  areas?: GardenArea[];
  hint?: string;
  onCancel: () => void;
  onSubmit: (input: NewPlantInput) => void;
  isSubmitting: boolean;
  isError: boolean;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState<GardenPlantType>("plant");
  const [species, setSpecies] = useState("");
  const [areaId, setAreaId] = useState<number | null>(areas?.[0]?.id ?? null);
  const needsArea = areas !== undefined;
  const canSubmit = name.trim() !== "" && (!needsArea || areaId !== null) && !isSubmitting;

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-lg bg-white p-4 shadow-lg">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) onSubmit({ name: name.trim(), type, species: species.trim(), areaId });
        }}
        className="flex flex-col gap-3"
      >
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Nieuwe plant</span>
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Naam" className={inputClass} />
        <input value={species} onChange={(e) => setSpecies(e.target.value)} placeholder="Soort (optioneel)" className={inputClass} />
        <select value={type} onChange={(e) => setType(e.target.value as GardenPlantType)} className={inputClass} aria-label="Type">
          {GARDEN_PLANT_TYPES.map((t) => (
            <option key={t} value={t}>
              {GARDEN_PLANT_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
        {needsArea &&
          (areas.length === 0 ? (
            <p className="text-sm text-slate-500">Maak eerst een tuin aan onder Tuinen.</p>
          ) : (
            <select value={areaId ?? ""} onChange={(e) => setAreaId(Number(e.target.value))} className={inputClass} aria-label="Tuin">
              {areas.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          ))}
        {hint && <p className="text-xs text-slate-500">{hint}</p>}
        {isError && <p className="text-sm text-red-600">Plant toevoegen is mislukt — probeer het opnieuw.</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="rounded-md px-3 py-2 text-sm font-medium text-slate-500 hover:text-slate-900">
            Annuleren
          </button>
          <button type="submit" disabled={!canSubmit} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
            {isSubmitting ? "Toevoegen…" : "Plant toevoegen"}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}
