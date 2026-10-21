import { Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import FontPicker from "./FontPicker";
import LanguagePicker from "./LanguagePicker";
import ModalOverlay from "./ModalOverlay";
import SettingsSection from "./ui/SettingsSection";
import { t } from "../i18n";

/** The gear for a module with no settings of its own (listr, gardnr, trainr, taskr, briefr, notr): just the preferences that
 * belong to the whole app. gainr and gripr open their own dialogs, which carry the same ones. */
export default function AppSettingsButton({ module }: { module: string }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("Settings")}
        title={t("Settings")}
        className="flex h-11 w-11 items-center justify-center rounded-xl text-ui-ink-soft hover:bg-ui-tile hover:text-ui-ink"
      >
        <Settings className="h-5 w-5" />
      </button>
      {open &&
        createPortal(
          <div className={`module-${module} contents`}>
            <ModalOverlay onClose={() => setOpen(false)} cardClassName="flex max-h-[90vh] w-full max-w-xl flex-col rounded-[28px] bg-white shadow-xl">
              <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
                <h2 className="text-lg font-semibold text-slate-900">{t("Settings")}</h2>
                <button type="button" onClick={() => setOpen(false)} aria-label={t("Close settings")} className="shrink-0 text-slate-500 hover:text-slate-800">
                  ✕
                </button>
              </div>
              <div className="flex flex-col gap-4 overflow-y-auto p-5">
                <SettingsSection title={t("Language")} tone="gainr">
                  <LanguagePicker />
                </SettingsSection>
                <SettingsSection title={t("Font")} tone="gainr">
                  <FontPicker />
                </SettingsSection>
              </div>
            </ModalOverlay>
          </div>,
          document.body,
        )}
    </>
  );
}
