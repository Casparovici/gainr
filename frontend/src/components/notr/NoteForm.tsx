import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { NOTR_KEYS, notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import { t } from "../../i18n";
import LabelPicker from "../LabelPicker";
import MarkdownEditor from "../MarkdownEditor";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "../ui/kit";
import LinkPicker, { type LinkIds } from "./LinkPicker";

export interface NoteFormDefaults {
  title?: string;
  body?: string;
  label_ids?: number[];
  pinned?: boolean;
  asset_ids?: number[];
  plant_ids?: number[];
  recipe_ids?: number[];
}

/** The skeleton of an investment thesis, for a note about a position. Written at the time it's
 * inserted, so it follows the language setting. */
function thesisTemplate(): string {
  return `## ${t("Why I own it")}\n\n\n## ${t("What would make me sell")}\n\n\n## ${t("Risks")}\n\n`;
}

/** Create or edit one note: title, Markdown body, labels, what it's about and whether it's pinned.
 * Saves itself through notrApi, refreshes every notes list and hands the saved note to `onSaved`.
 * Used by notr's own page and by the Notes sections on a position, a plant and a recipe, which
 * pass `fixedLinks` since they already know what the note is about. */
export default function NoteForm({
  note,
  defaults,
  fixedLinks = false,
  requireAsset = false,
  autoFocus = false,
  onSaved,
  onCancel,
}: {
  note?: NotrNote;
  defaults?: NoteFormDefaults;
  fixedLinks?: boolean;
  requireAsset?: boolean;
  autoFocus?: boolean;
  onSaved: (note: NotrNote) => void;
  onCancel: () => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(note?.title ?? defaults?.title ?? "");
  const [body, setBody] = useState(note?.body ?? defaults?.body ?? "");
  const [pinned, setPinned] = useState(note?.pinned ?? defaults?.pinned ?? false);
  const [labelIds, setLabelIds] = useState<number[]>(note?.labels.map((l) => l.id) ?? defaults?.label_ids ?? []);
  const [links, setLinks] = useState<LinkIds>({
    asset_ids: note?.assets.map((a) => a.id) ?? defaults?.asset_ids ?? [],
    plant_ids: note?.plants.map((p) => p.id) ?? defaults?.plant_ids ?? [],
    recipe_ids: note?.recipes.map((r) => r.id) ?? defaults?.recipe_ids ?? [],
  });

  const save = useMutation({
    mutationFn: () => {
      const common = { title: title.trim(), body, pinned, label_ids: labelIds };
      // A caller that fixes the links leaves them alone on an edit (omitting a list changes nothing).
      if (note) return notrApi.updateNote(note.id, fixedLinks ? common : { ...common, ...links });
      return notrApi.createNote({ ...common, ...links });
    },
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: NOTR_KEYS.all });
      onSaved(saved);
    },
  });

  const hasContent = title.trim() !== "" || body.trim() !== "";
  const missingAsset = requireAsset && links.asset_ids.length === 0;
  const canSave = hasContent && !missingAsset && !save.isPending;
  const offerTemplate = !note && links.asset_ids.length > 0 && body.trim() === "";

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSave) save.mutate();
      }}
      className="flex flex-col gap-4"
    >
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder={t("Title (optional)")}
        aria-label={t("Title")}
        autoFocus={autoFocus}
        className={`${inputClass} font-semibold`}
      />

      {offerTemplate && (
        <button
          type="button"
          onClick={() => setBody(thesisTemplate())}
          className="self-start text-sm font-semibold text-ui-brand-strong underline underline-offset-2"
        >
          {t("Start from the thesis template")}
        </button>
      )}

      <MarkdownEditor value={body} onChange={setBody} placeholder={t("Write your note…")} />

      <section className="flex flex-col gap-2" aria-label={t("Labels")}>
        <h3 className="m-0 text-sm font-semibold text-ui-ink">{t("Labels")}</h3>
        <LabelPicker selectedIds={labelIds} onChange={setLabelIds} />
      </section>

      {!fixedLinks && (
        <section className="flex flex-col gap-2" aria-label={t("About")}>
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="m-0 text-sm font-semibold text-ui-ink">{t("About")}</h3>
            {requireAsset && <span className="text-xs text-ui-muted">{t("pick at least one position")}</span>}
          </div>
          <LinkPicker value={links} known={note} onChange={setLinks} />
        </section>
      )}

      <label className="flex min-h-11 cursor-pointer items-center gap-3 text-[15px] text-ui-ink">
        <input
          type="checkbox"
          checked={pinned}
          onChange={(e) => setPinned(e.target.checked)}
          className="h-5 w-5 accent-[rgb(var(--ui-brand-rgb))]"
        />
        {t("Pin this note")}
      </label>

      {save.isError && (
        <p className="m-0 text-sm text-ui-late" role="alert">
          {t("Couldn't save the note. Try again.")}
        </p>
      )}

      <div className="flex gap-2">
        <button type="button" onClick={onCancel} className={`${secondaryButtonClass} flex-1 sm:flex-none`}>
          {t("Cancel")}
        </button>
        <button
          type="submit"
          disabled={!canSave}
          title={missingAsset ? t("Pick at least one position") : undefined}
          className={`${primaryButtonClass} flex-1 sm:flex-none`}
        >
          {save.isPending ? t("Saving…") : t("Save")}
        </button>
      </div>
    </form>
  );
}
