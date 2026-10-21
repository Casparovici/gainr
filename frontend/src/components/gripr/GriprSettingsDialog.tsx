import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { griprApi } from "../../api/griprClient";
import ModalOverlay from "../ModalOverlay";
import { inputClass } from "../ui/kit";
import FontPicker from "../FontPicker";
import LanguagePicker from "../LanguagePicker";
import SettingsSection from "../ui/SettingsSection";
import BankSettings from "./BankSettings";
import GriprButton from "./GriprButton";
import { t } from "../../i18n";

/** gripr's settings, in one place: when a period starts, and the bank connections. Opened from the
 * gear on Accounts, and from the gear next to the period switcher on Budget and Overview -- the
 * same dialog either way, so there's one settings screen to learn rather than a popover here and
 * a card there. `onPeriodSaved` lets a page showing a period jump to the one containing today
 * once the start day changes, since the period it was showing may not exist under the new day. */
export default function GriprSettingsDialog({
  onClose,
  onPeriodSaved,
}: {
  onClose: () => void;
  onPeriodSaved?: (startDay: number) => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="module-gripr contents">
      <ModalOverlay onClose={onClose} cardClassName="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-[28px] bg-surface shadow-xl">
        <div className="flex items-center justify-between gap-3 border-b border-outline-variant px-5 py-4">
          <h2 className="text-lg font-semibold text-on-surface">{t("Settings")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close settings")} className="shrink-0 text-on-surface-variant hover:text-on-surface">
            ✕
          </button>
        </div>
        <div className="flex flex-col gap-3 overflow-y-auto p-5">
          <SettingsSection title={t("Period")}>
            <PeriodSettings onSaved={onPeriodSaved} />
          </SettingsSection>
          <SettingsSection title={t("Language")}>
            <LanguagePicker tone="gripr" />
          </SettingsSection>
          <SettingsSection title={t("Font")}>
            <FontPicker tone="gripr" />
          </SettingsSection>
          <BankSettings />
        </div>
      </ModalOverlay>
    </div>,
    document.body,
  );
}

function PeriodSettings({ onSaved }: { onSaved?: (startDay: number) => void }) {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: ["gripr-settings"], queryFn: () => griprApi.getSettings() });
  const [draft, setDraft] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const current = settingsQuery.data?.period_start_day;
  const value = draft ?? (current !== undefined ? String(current) : "");
  const parsed = Number(value);
  const valid = Number.isInteger(parsed) && parsed >= 1 && parsed <= 28;

  const saveMutation = useMutation({
    mutationFn: (day: number) => griprApi.updateSettings({ period_start_day: day }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["gripr-settings"] });
      setDraft(null);
      setSaved(true);
      onSaved?.(data.period_start_day);
    },
  });

  if (settingsQuery.isError) {
    return <p className="text-sm text-error">{t("Couldn't load the period setting. Close and reopen settings to try again.")}</p>;
  }
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) saveMutation.mutate(parsed);
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
      <label className="flex flex-wrap items-center gap-2 text-sm text-on-surface">{t("A period starts on day")}<input
          type="number"
          min={1}
          max={28}
          aria-label={t("Period start day")}
          value={value}
          disabled={settingsQuery.isLoading}
          onChange={(e) => {
            setDraft(e.target.value);
            setSaved(false);
          }}
          className={inputClass.replace("w-full", "w-20 shrink-0")}
        />{t("of the month")}</label>
        {draft !== null && draft !== String(current) && (
          <GriprButton type="submit" variant="tonal" disabled={!valid || saveMutation.isPending}>
            {saveMutation.isPending ? t("Saving…") : t("Save")}
          </GriprButton>
        )}
      </div>
      <p className="text-xs text-on-surface-variant">{t("Budget and Overview count periods from this day — payday, say, rather than the 1st (1–28, so every month has it). Budgets you've already set keep the periods they were set for.")}{saved && ` ${t("Saved.")}`}
        {saveMutation.isError && ` ${t("Saving didn't work — try again.")}`}
      </p>
    </form>
  );
}
