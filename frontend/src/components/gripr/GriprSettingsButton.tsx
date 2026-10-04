import { Settings } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import GriprSettingsDialog from "./GriprSettingsDialog";

/** The gear that opens gripr's settings (period, banks) from the Accounts page. A bank that needs
 * attention shows up in the notifications bell (GriprNotifications), not on the gear. A bank's
 * redirect back after a consent (?bank=...) opens the settings straight away, where the outcome is
 * shown. */
export default function GriprSettingsButton({ onPeriodSaved }: { onPeriodSaved?: (startDay: number) => void }) {
  const [searchParams] = useSearchParams();
  const [open, setOpen] = useState(() => searchParams.has("bank"));
  const label = "Settings";

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={label}
        title={label}
        className="relative flex h-11 w-11 items-center justify-center rounded-xl text-on-surface-variant hover:bg-on-surface/10 hover:text-on-surface"
      >
        <Settings className="h-5 w-5" />
      </button>
      {open && <GriprSettingsDialog onClose={() => setOpen(false)} onPeriodSaved={onPeriodSaved} />}
    </>
  );
}
