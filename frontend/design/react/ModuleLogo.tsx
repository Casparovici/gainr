// Module logos for gainr / gripr / listr / gardnr / trainr / taskr / briefr / notr.
// Glyphs are drawn on a 48x48 grid, white stroke on a coloured tile.
import type { SVGProps } from "react";

export type ModuleKey = "gainr" | "gripr" | "listr" | "gardnr" | "trainr" | "taskr" | "briefr" | "notr";

export const MODULE_BRAND: Record<ModuleKey, { color: string; colorDark: string; label: string }> = {
  gainr: { color: "#3F3AC4", colorDark: "#9D9AF2", label: "Beleggingsportefeuille" },
  gripr: { color: "#B7790A", colorDark: "#EDB94A", label: "Persoonlijke financiën" },
  listr: { color: "#D4502A", colorDark: "#F08A66", label: "Boodschappen & recepten" },
  gardnr: { color: "#2F7D3A", colorDark: "#7FC486", label: "Tuin & verzorging" },
  trainr: { color: "#1769AA", colorDark: "#7DB8E8", label: "Sport & training" },
  taskr: { color: "#A3307A", colorDark: "#EFA2D2", label: "Agenda over alle modules" },
  briefr: { color: "#0B7A75", colorDark: "#6FD3CB", label: "Rapporten van je agents" },
  notr: { color: "#5E7F12", colorDark: "#B7D86A", label: "Notities en ideeën" },
};

const GLYPHS: Record<ModuleKey, JSX.Element> = {
  gainr: <><polyline points="10,34 19,25 26,31 37,18" fill="none"/><polyline points="29,17 38,17 38,26" fill="none"/></>,
  gripr: <><path d="M17 12 A14 14 0 0 0 17 36" fill="none"/><path d="M31 12 A14 14 0 0 1 31 36" fill="none"/><circle cx="24" cy="24" r="6" fill="currentColor" stroke="none"/></>,
  listr: <><polyline points="10,15 13,18 18,12" fill="none"/><line x1="23" y1="15" x2="38" y2="15"/><polyline points="10,25 13,28 18,22" fill="none"/><line x1="23" y1="25" x2="38" y2="25"/><circle cx="14" cy="34" r="3" fill="none"/><line x1="23" y1="34" x2="33" y2="34"/></>,
  gardnr: <><line x1="24" y1="37" x2="24" y2="23"/><path d="M24 28 C15 28 11 22 12 16 C19 16 24 20 24 28 Z" fill="currentColor"/><path d="M24 23 C24 16 29 11 36 12 C36 19 31 23 24 23 Z" fill="none"/><line x1="15" y1="37" x2="33" y2="37"/></>,
  trainr: <><line x1="16" y1="24" x2="32" y2="24"/><line x1="16" y1="14" x2="16" y2="34"/><line x1="32" y1="14" x2="32" y2="34"/><line x1="10" y1="19" x2="10" y2="29"/><line x1="38" y1="19" x2="38" y2="29"/></>,
  taskr: <><rect x="10" y="12" width="28" height="26" rx="4" fill="none"/><line x1="10" y1="20" x2="38" y2="20"/><line x1="17" y1="8" x2="17" y2="14"/><line x1="31" y1="8" x2="31" y2="14"/><polyline points="17,29 22,33 31,25" fill="none"/></>,
  briefr: <><path d="M13 11 A3 3 0 0 1 16 8 H28 L35 15 V37 A3 3 0 0 1 32 40 H16 A3 3 0 0 1 13 37 Z" fill="none"/><polyline points="28,8 28,15 35,15" fill="none"/><line x1="19" y1="23" x2="29" y2="23"/><line x1="19" y1="29" x2="29" y2="29"/><line x1="19" y1="35" x2="25" y2="35"/></>,
  notr: <><rect x="11" y="11" width="26" height="28" rx="4" fill="none"/><line x1="18" y1="7" x2="18" y2="14"/><line x1="30" y1="7" x2="30" y2="14"/><line x1="18" y1="23" x2="30" y2="23"/><line x1="18" y1="30" x2="26" y2="30"/></>,
};

/** Just the line symbol; inherits `currentColor` (Lucide-style). */
export function ModuleGlyph({ module, size = 24, ...rest }: { module: ModuleKey; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" stroke="currentColor"
      strokeWidth={size <= 32 ? 4.2 : 3.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      {GLYPHS[module]}
    </svg>
  );
}

/** The app icon: coloured rounded tile (or circle) with the white glyph. */
export function ModuleIcon({ module, size = 32, round = false, className = "" }: { module: ModuleKey; size?: number; round?: boolean; className?: string }) {
  return (
    <span className={`inline-flex shrink-0 items-center justify-center text-white ${className}`}
      style={{ width: size, height: size, borderRadius: round ? "50%" : size * 0.26, background: MODULE_BRAND[module].color }}>
      <ModuleGlyph module={module} size={Math.round(size * 0.72)} />
    </span>
  );
}

/** Lowercase wordmark; the final "r" carries the module colour. Font: Bricolage Grotesque 700. */
export function ModuleWordmark({ module, dark = false, className = "" }: { module: ModuleKey; dark?: boolean; className?: string }) {
  const b = MODULE_BRAND[module];
  return (
    <span className={`font-bold tracking-tight ${className}`} style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
      {module.slice(0, -1)}<span style={{ color: dark ? b.colorDark : b.color }}>r</span>
    </span>
  );
}
