import { ChevronDown, LayoutGrid } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import type { Today } from "../api/taskrTypes";
import { activeModule, MODULES, type ModuleDef } from "../config/modules";
import { useToday } from "../hooks/useToday";
import { formatPct, toNumber } from "../utils/format";
import { isModuleKey, MODULE_BRAND, ModuleIcon, ModuleWordmark } from "./ModuleLogo";
import ThemeToggle from "./ThemeToggle";
import Sheet from "./ui/Sheet";
import { t, tp } from "../i18n";

const CLOSE_DELAY_MS = 150;

/** What waits in a module: a count worth a badge (`urgent` ones in the late colour) and a short
 * line for its tile. From Vandaag's data, so the switcher and the start screen agree. */
export interface ModuleStatus {
  count: number;
  hint: string | null;
  urgent?: boolean;
}

export function moduleStatus(key: string, today: Today | undefined): ModuleStatus {
  if (!today) return { count: 0, hint: null };
  const c = today.counts;

  switch (key) {
    case "vandaag": {
      const waiting = [c.gardnr_due, c.taskr_overdue, c.gripr_uncategorized, c.briefr_unread].filter((n) => n > 0).length;
      return { count: 0, hint: waiting ? tp(waiting, "{n} ding vraagt aandacht", "{n} dingen vragen aandacht") : t("Alles bij") };
    }
    case "gainr": {
      const pct = today.portfolio?.day_change_pct ?? null;
      return { count: 0, hint: toNumber(pct) === null ? null : t("{pct} vandaag", { pct: formatPct(pct) }) };
    }
    case "gripr":
      return { count: c.gripr_uncategorized, hint: c.gripr_uncategorized ? t("{n} zonder categorie", { n: c.gripr_uncategorized }) : null };
    case "listr":
      return { count: 0, hint: c.listr_to_get ? t("{n} op de lijst", { n: c.listr_to_get }) : null };
    case "gardnr":
      return { count: c.gardnr_due, hint: c.gardnr_due ? t("{n} te doen", { n: c.gardnr_due }) : null, urgent: today.agenda.overdue.some((i) => i.source === "gardnr") };
    case "trainr":
      return { count: c.trainr_today, hint: c.trainr_today ? tp(c.trainr_today, "{n} workout vandaag", "{n} workouts vandaag") : null };
    case "briefr":
      return { count: c.briefr_unread, hint: c.briefr_unread ? t("{n} ongelezen", { n: c.briefr_unread }) : null };
    case "notr":
      // Pinned notes aren't "waiting" for anything, so no badge -- just a line on the tile.
      return { count: 0, hint: c.notr_pinned ? t("{n} vastgezet", { n: c.notr_pinned }) : null };
    default:
      return { count: 0, hint: null };
  }
}

/** A module's logo tile + wordmark -- or, for Vandaag (which is no module), a neutral grid tile. */
function ModuleMark({ module, iconSize, wordmarkClass = "text-base" }: { module: ModuleDef; iconSize: number; wordmarkClass?: string }) {
  if (!isModuleKey(module.key)) {
    return (
      <>
        <span
          aria-hidden
          className="flex shrink-0 items-center justify-center bg-ui-ink text-ui-surface"
          style={{ width: iconSize, height: iconSize, borderRadius: iconSize * 0.26 }}
        >
          <LayoutGrid style={{ width: iconSize * 0.56, height: iconSize * 0.56 }} strokeWidth={2.2} />
        </span>
        <span className={`font-display font-bold tracking-[-0.02em] ${wordmarkClass}`}>{t(module.label)}</span>
      </>
    );
  }
  return (
    <>
      <ModuleIcon module={module.key} size={iconSize} />
      <ModuleWordmark module={module.key} className={wordmarkClass} />
    </>
  );
}

function CountBadge({ status }: { status: ModuleStatus }) {
  if (status.count <= 0) return null;
  return (
    <span
      className={`flex h-[22px] min-w-[22px] items-center justify-center rounded-full px-1.5 text-xs font-bold text-white ${
        status.urgent ? "bg-ui-late" : "bg-ui-ink"
      }`}
    >
      {status.count > 99 ? "99+" : status.count}
    </span>
  );
}

/** Getting from one module to another. On a phone (`variant="pill"`, the 44px pill in each page's
 * top row) it opens a sheet of tiles, Vandaag first, each with what waits there; the theme switch
 * rides along, since the header that normally holds it is hidden there. From tablet width up it's
 * the header's menu, opening on hover, with the same counts. taskr has no tile: Vandaag shows its
 * agenda and links to it. */
export default function ModuleSwitcher({ variant = "default" }: { variant?: "default" | "pill" }) {
  const pathname = useLocation().pathname;
  const active = activeModule(pathname);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | null>(null);
  const { data: today } = useToday();
  const listed = MODULES.filter((m) => !m.hidden);
  const anyWaiting = listed.some((m) => moduleStatus(m.key, today).count > 0 && m.key !== active.key);

  function cancelClose() {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }

  function scheduleClose() {
    cancelClose();
    closeTimer.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  }

  useEffect(() => cancelClose, []);

  useEffect(() => {
    if (!open || variant === "pill") return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open, variant]);

  if (variant === "pill") {
    return (
      <>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="relative flex h-11 items-center gap-2 rounded-full border border-ui-border bg-ui-surface pl-1.5 pr-3 text-ui-ink"
          aria-haspopup="dialog"
          aria-label={t("{module} — naar een andere module", { module: t(active.label) })}
        >
          <ModuleMark module={active} iconSize={30} wordmarkClass="text-[17px]" />
          <ChevronDown className="h-4 w-4 text-ui-muted" strokeWidth={2} />
          {anyWaiting && <span aria-hidden className="absolute right-1 top-1 h-2.5 w-2.5 rounded-full border-2 border-ui-surface bg-ui-late" />}
        </button>
        {open && (
          <Sheet title={t("Naar module")} onClose={() => setOpen(false)}>
            <nav aria-label={t("Modules")} className="flex flex-col gap-3 pb-1 pt-2">
              {listed
                .filter((m) => m.key === "vandaag")
                .map((m) => (
                  <Link
                    key={m.key}
                    to={m.path}
                    onClick={() => setOpen(false)}
                    aria-current={m.key === active.key ? "page" : undefined}
                    className="flex h-14 items-center gap-3 rounded-2xl bg-ui-tile px-3.5 text-ui-ink no-underline"
                  >
                    <ModuleMark module={m} iconSize={32} wordmarkClass="text-[17px]" />
                    <span className="ml-auto text-[13px] font-semibold text-ui-muted">{moduleStatus(m.key, today).hint}</span>
                  </Link>
                ))}
              <div className="grid grid-cols-3 gap-2.5">
                {listed
                  .filter((m) => m.key !== "vandaag")
                  .map((m) => {
                    const status = moduleStatus(m.key, today);
                    return (
                      <Link
                        key={m.key}
                        to={m.path}
                        onClick={() => setOpen(false)}
                        aria-current={m.key === active.key ? "page" : undefined}
                        aria-label={status.hint ? `${t(m.label)}, ${status.hint}` : t(m.label)}
                        className={`relative flex min-w-0 flex-col items-center gap-1.5 rounded-2xl border px-1.5 pb-2.5 pt-3.5 text-ui-ink no-underline ${
                          m.key === active.key ? "border-ui-ink/40 bg-ui-tile" : "border-ui-border"
                        }`}
                      >
                        {isModuleKey(m.key) && <ModuleIcon module={m.key} size={44} />}
                        <span className="font-display text-[15px] font-bold tracking-[-0.01em]">{t(m.label)}</span>
                        <span className="h-4 w-full truncate text-center text-xs text-ui-muted">{status.hint ?? ""}</span>
                        <span className="absolute right-2 top-2">
                          <CountBadge status={status} />
                        </span>
                      </Link>
                    );
                  })}
              </div>
              <div className="mt-1 flex items-center justify-between gap-3 border-t border-ui-line/60 pt-3">
                <span className="text-sm font-semibold text-ui-muted">{t("Thema")}</span>
                <ThemeToggle />
              </div>
            </nav>
          </Sheet>
        )}
      </>
    );
  }

  // Real mouse only -- a touch tap also synthesizes hover/leave events for :hover-CSS
  // compatibility, which would otherwise open the panel via "enter" and then immediately
  // schedule it closed via "leave" a moment later. Touch gets in via the button's onClick below.
  function handlePointerEnter(e: React.PointerEvent) {
    if (e.pointerType !== "mouse") return;
    cancelClose();
    setOpen(true);
  }
  function handlePointerLeave(e: React.PointerEvent) {
    if (e.pointerType !== "mouse") return;
    scheduleClose();
  }

  return (
    <div
      ref={containerRef}
      className="relative"
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      <button
        type="button"
        // Not a toggle: on a real mouse, hovering the button to reach it already opens the
        // panel via onPointerEnter, so a naive toggle would immediately close what hover just
        // opened. A click only ever needs to *ensure* it's open (the case that matters is touch,
        // which gets no hover at all); closing is outside-click/pointer-leave's job.
        onClick={() => setOpen(true)}
        className="relative flex items-center gap-2 rounded-xl py-1 pl-1 pr-2 text-slate-900 transition-colors hover:bg-slate-100"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={t("{module} — switch module", { module: t(active.label) })}
      >
        <ModuleMark module={active} iconSize={28} />
        <ChevronDown className="h-3.5 w-3.5 text-slate-500" strokeWidth={2} />
        {anyWaiting && <span aria-hidden className="absolute left-6 top-0 h-2.5 w-2.5 rounded-full border-2 border-ui-surface bg-ui-late" />}
      </button>

      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 min-w-[16rem] overflow-hidden rounded-xl border border-ui-border bg-ui-surface p-1 shadow-lg">
          {listed.map((m) => {
            const status = moduleStatus(m.key, today);
            return (
              <Link
                key={m.key}
                to={m.path}
                onClick={() => setOpen(false)}
                title={isModuleKey(m.key) ? t(MODULE_BRAND[m.key].label) : undefined}
                aria-current={m.key === active.key ? "page" : undefined}
                className={`flex items-center gap-2 whitespace-nowrap rounded-lg py-1 pl-1 pr-2 text-ui-ink no-underline transition-colors ${
                  m.key === active.key ? "bg-ui-tile" : "hover:bg-ui-tile/60"
                }`}
              >
                <ModuleMark module={m} iconSize={28} />
                <span className="ml-auto pl-3 text-xs text-ui-muted">{status.hint}</span>
                <CountBadge status={status} />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
