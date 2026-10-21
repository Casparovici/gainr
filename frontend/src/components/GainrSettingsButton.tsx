import { Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { usePortfolio } from "../hooks/usePortfolio";
import FontPicker from "./FontPicker";
import ModalOverlay from "./ModalOverlay";
import SettingsSection from "./ui/SettingsSection";
import Trading212Sync from "./Trading212Sync";
import { t } from "../i18n";

/** The gear that opens gainr's settings -- today the Trading 212 sync -- from the top row of every
 * gainr page, like gripr's. Problems with the sync show in the notifications bell. */
export default function GainrSettingsButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("Settings")}
        title={t("Settings")}
        className="flex h-11 w-11 items-center justify-center rounded-xl text-slate-500 hover:bg-slate-900/5 hover:text-slate-800"
      >
        <Settings className="h-5 w-5" />
      </button>
      {open && <GainrSettingsDialog onClose={() => setOpen(false)} />}
    </>
  );
}

function GainrSettingsDialog({ onClose }: { onClose: () => void }) {
  const { portfolioId, portfolios } = usePortfolio();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="module-gainr contents">
      <ModalOverlay onClose={onClose} cardClassName="flex max-h-[90vh] w-full max-w-xl flex-col rounded-[28px] bg-white shadow-xl">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-semibold text-slate-900">{t("Settings")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close settings")} className="shrink-0 text-slate-500 hover:text-slate-800">
            ✕
          </button>
        </div>
        <div className="flex flex-col gap-4 overflow-y-auto p-5">
          <SettingsSection title={t("Font")} tone="gainr">
            <FontPicker />
          </SettingsSection>
          {portfolioId !== null ? (
            <Trading212Sync portfolioId={portfolioId} portfolioName={portfolios.find((p) => p.id === portfolioId)?.name ?? t("this portfolio")} />
          ) : (
            <p className="text-sm text-slate-500">{t("Loading…")}</p>
          )}
        </div>
      </ModalOverlay>
    </div>,
    document.body,
  );
}
