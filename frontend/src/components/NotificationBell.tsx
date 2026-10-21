import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowDownLeft, Bell, Clock, Download, Link2Off } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { AppNotification } from "../api/types";
import { formatRelativeTime } from "../utils/format";
import ModalOverlay from "./ModalOverlay";
import { t } from "../i18n";

function readSeenAt(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // private window or blocked storage: everything from the last week counts as new
  }
}

function writeSeenAt(key: string, iso: string) {
  try {
    localStorage.setItem(key, iso);
  } catch {
    // Nothing to do: the dot just comes back next time.
  }
}

const ICONS = {
  synced: Download,
  money_back: ArrowDownLeft,
  still_owed: Clock,
  bank: AlertTriangle,
  broker: AlertTriangle,
  unmapped: Link2Off,
} as const;

/** A module's notifications bell: a dot when something happened since this device last opened it.
 * Opening shows the list; closing it marks everything seen. The "last looked" time is kept per
 * device (and per module, under `storageKey`), so opening the bell on one phone doesn't clear it
 * on another, or on someone else's. gripr's items come from its bank syncs, repayments and
 * reminders; gainr's from the Trading 212 sync. */
export default function NotificationBell({
  storageKey,
  queryKey,
  load,
}: {
  storageKey: string;
  queryKey: string;
  load: (since: string | null) => Promise<AppNotification[]>;
}) {
  const [seenAt, setSeenAt] = useState(() => readSeenAt(storageKey));
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: [queryKey, seenAt], queryFn: () => load(seenAt) });
  const items = query.data ?? [];
  const isNew = (n: AppNotification) => seenAt === null || Date.parse(n.at) > Date.parse(seenAt);
  const unseen = items.filter(isNew).length;

  function close() {
    setOpen(false);
    const now = new Date().toISOString();
    writeSeenAt(storageKey, now);
    setSeenAt(now);
  }

  const label = unseen ? t("Notifications — {n} new", { n: unseen })
 : t("Notifications");
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={label}
        title={label}
        className="relative flex h-11 w-11 items-center justify-center rounded-xl text-on-surface-variant hover:bg-on-surface/10 hover:text-on-surface"
      >
        <Bell className="h-5 w-5" />
        {unseen > 0 && <span aria-hidden className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-error ring-2 ring-surface" />}
      </button>
      {open && (
        <ModalOverlay onClose={close} cardClassName="flex max-h-[80vh] w-full max-w-md flex-col rounded-[28px] bg-surface shadow-xl">
          <div className="flex items-center justify-between gap-3 border-b border-outline-variant px-5 py-4">
            <h2 className="text-lg font-medium text-on-surface">{t("Since your last visit")}</h2>
            <button type="button" onClick={close} className="text-sm font-medium text-primary hover:underline">{t("Done")}</button>
          </div>
          <div className="overflow-y-auto px-5 py-3">
            {query.isLoading ? (
              <p className="py-4 text-sm text-on-surface-variant">{t("Loading…")}</p>
            ) : query.isError ? (
              <p className="py-4 text-sm text-error">{t("Couldn't load what's new. Close this and try again.")}</p>
            ) : items.length === 0 ? (
              <p className="py-4 text-sm text-on-surface-variant">{t("Nothing new. Synced transactions, money coming back and bank problems show up here.")}</p>
            ) : (
              <ul className="divide-y divide-outline-variant">
                {items.map((n) => {
                  const Icon = ICONS[n.kind] ?? AlertTriangle;
                  return (
                    <li key={n.key}>
                      <Link to={n.link} onClick={close} className="flex items-start gap-3 py-3 hover:bg-on-surface/5">
                        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${["bank", "broker", "unmapped"].includes(n.kind) ? "text-error" : "text-on-surface-variant"}`} aria-hidden />
                        <span className="min-w-0 flex-1">
                          <span className={`block text-sm text-on-surface ${isNew(n) ? "font-semibold" : ""}`}>{n.title}</span>
                          {n.detail && <span className="block text-xs text-on-surface-variant">{n.detail}</span>}
                        </span>
                        <span className="shrink-0 text-xs text-on-surface-variant">{formatRelativeTime(n.at)}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </ModalOverlay>
      )}
    </>
  );
}
