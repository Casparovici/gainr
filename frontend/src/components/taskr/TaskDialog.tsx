import { useState } from "react";

import type { TaskrTaskInput } from "../../api/taskrTypes";
import ModalOverlay from "../ModalOverlay";
import { dangerButtonClass, inputClass, primaryButtonClass, secondaryButtonClass } from "../ui/kit";
import { t } from "../../i18n";

const labelClass = "text-xs font-medium uppercase tracking-wide text-slate-500";

/** Changes or deletes a taskr task: its title, day and notes. Adding happens in the agenda's own
 * quick-add row, which needs only a title and a day. */
export default function TaskDialog({
  task,
  isSubmitting,
  error,
  onSave,
  onDelete,
  onCancel,
}: {
  task: TaskrTaskInput;
  isSubmitting: boolean;
  error: string | null;
  onSave: (input: TaskrTaskInput) => void;
  onDelete: () => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(task.title);
  const [dueDate, setDueDate] = useState(task.due_date);
  const [notes, setNotes] = useState(task.notes ?? "");

  return (
    <ModalOverlay onClose={onCancel} cardClassName="flex max-h-[90vh] w-full max-w-lg flex-col rounded-lg bg-white shadow-lg">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) onSave({ title: title.trim(), due_date: dueDate, notes: notes.trim() || null });
        }}
        className="flex min-h-0 flex-col"
      >
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-900">{t("Taak wijzigen")}</h2>
        </div>

        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-5 py-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className={labelClass}>{t("Taak")}</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} className={inputClass} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className={labelClass}>{t("Datum")}</span>
            <input type="date" value={dueDate} onChange={(e) => e.target.value && setDueDate(e.target.value)} required className={inputClass} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className={labelClass}>{t("Notitie")}</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} maxLength={2000} className={`${inputClass.replace("h-11 ", "")} py-2`} />
          </label>
          {error && <p className="m-0 text-sm text-red-600">{error}</p>}
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-5 py-3">
          <button
            type="button"
            onClick={() => {
              if (confirm(t("\"{title}\" verwijderen? Hij verdwijnt uit de agenda; afvinken bewaart hem wel.", { title: task.title }))) onDelete();
            }}
            disabled={isSubmitting}
            className={dangerButtonClass}
          >{t("Verwijderen")}</button>
          <div className="flex gap-2">
            <button type="button" onClick={onCancel} className={secondaryButtonClass}>{t("Annuleren")}</button>
            <button type="submit" disabled={isSubmitting || !title.trim()} className={primaryButtonClass}>
              {isSubmitting ? t("Opslaan…") : t("Opslaan")}
            </button>
          </div>
        </div>
      </form>
    </ModalOverlay>
  );
}
