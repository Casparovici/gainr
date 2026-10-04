import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { activeModule, MODULES, type ModuleDef } from "../config/modules";
import { isModuleKey, MODULE_BRAND, ModuleIcon, ModuleWordmark } from "./ModuleLogo";
import ThemeToggle from "./ThemeToggle";

const CLOSE_DELAY_MS = 150;

/** A module's logo tile + wordmark -- or its plain label, for a module without a brand entry. */
function ModuleMark({ module, iconSize, wordmarkClass = "text-base" }: { module: ModuleDef; iconSize: number; wordmarkClass?: string }) {
  if (!isModuleKey(module.key)) return <>{module.label}</>;
  return (
    <>
      <ModuleIcon module={module.key} size={iconSize} />
      <ModuleWordmark module={module.key} className={wordmarkClass} />
    </>
  );
}

/** Collapsed to just the active module by default, so a fourth or fifth entry in MODULES never
 * costs more header width. Hovering the pill expands the full list below it; picking one
 * navigates and collapses it again. */
/** `variant="pill"` is the white, bordered 44px pill gardnr's redesign puts in its pages' own
 * top row on a phone (see ModuleTopRow); the default is the plain header version. The pill's
 * menu also carries the theme toggle, since the header that normally holds it is hidden there. */
export default function ModuleSwitcher({ variant = "default" }: { variant?: "default" | "pill" }) {
  const pathname = useLocation().pathname;
  const active = activeModule(pathname);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | null>(null);

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
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

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
        className={
          variant === "pill"
            ? "flex h-11 items-center gap-2 rounded-full border border-ui-border bg-ui-surface pl-1.5 pr-3 text-ui-ink"
            : "flex items-center gap-2 rounded-xl py-1 pl-1 pr-2 text-slate-900 transition-colors hover:bg-slate-100"
        }
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`${active.label} — switch module`}
      >
        <ModuleMark module={active} iconSize={variant === "pill" ? 30 : 28} wordmarkClass={variant === "pill" ? "text-[17px]" : "text-base"} />
        <ChevronDown className={variant === "pill" ? "h-4 w-4 text-ui-muted" : "h-3.5 w-3.5 text-slate-500"} strokeWidth={2} />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 min-w-full overflow-hidden rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          {MODULES.map((m) => (
            <Link
              key={m.key}
              to={m.path}
              onClick={() => setOpen(false)}
              title={isModuleKey(m.key) ? MODULE_BRAND[m.key].label : undefined}
              aria-current={m.key === active.key ? "page" : undefined}
              className={`flex items-center gap-2 whitespace-nowrap rounded-md py-1 pl-1 pr-3 text-slate-900 transition-colors ${
                m.key === active.key ? "bg-slate-100" : "hover:bg-slate-50"
              }`}
            >
              <ModuleMark module={m} iconSize={28} />
            </Link>
          ))}
          {variant === "pill" && (
            <div className="mt-1 flex items-center justify-between gap-3 border-t border-slate-100 px-2 pb-1 pt-2">
              <span className="text-xs font-medium text-slate-500">Theme</span>
              <ThemeToggle />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
