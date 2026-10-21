import { useState } from "react";

import type { GriprCategory, GriprCategoryKind } from "../../api/griprTypes";
import ModalOverlay from "../ModalOverlay";
import { t } from "../../i18n";

const inputClass =
  "rounded-md border border-outline px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

/** Short form for a new category of one kind, top-level or filed under an existing parent --
 * opened from the "+ Add category" tile at the end of a Budget tab. */
export default function NewCategoryForm({
  kind,
  parents,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  kind: GriprCategoryKind;
  parents: GriprCategory[];
  onCancel: () => void;
  onSubmit: (input: { name: string; kind: GriprCategoryKind; parent_id: number | null }) => void;
  isSubmitting: boolean;
}) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState<string>("");

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-[28px] bg-surface p-6 shadow-xl">
        <h2 className="text-lg font-medium text-on-surface">{kind === "income" ? t("New income category") : t("New expense category")}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit({ name, kind, parent_id: parentId ? Number(parentId) : null });
          }}
          className="mt-4 flex flex-col gap-3"
        >
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{t("Name")}</span>
            <input required autoFocus value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{t("Parent (optional)")}</span>
            <select value={parentId} onChange={(e) => setParentId(e.target.value)} className={inputClass}>
              <option value="">{t("— top-level category —")}</option>
              {parents.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full border border-outline px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
            >{t("Cancel")}</button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:opacity-90 disabled:opacity-50"
            >
              {isSubmitting ? t("Saving…") : t("Create")}
            </button>
          </div>
        </form>
    </ModalOverlay>
  );
}
