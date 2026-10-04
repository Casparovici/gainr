import { useState } from "react";

import ModalOverlay from "../ModalOverlay";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

export default function NewListForm({
  title = "Nieuwe lijst",
  initialName = "",
  isSubmitting,
  onCancel,
  onSubmit,
}: {
  title?: string;
  initialName?: string;
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (name: string) => void;
}) {
  const [name, setName] = useState(initialName);

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onSubmit(name.trim());
        }}
        className="mt-4 flex flex-col gap-3"
      >
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Naam</span>
          <input
            required
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Weekboodschappen, BBQ, …"
            className={inputClass}
          />
        </label>
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
            disabled={isSubmitting}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isSubmitting ? "Bezig…" : "Opslaan"}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}
