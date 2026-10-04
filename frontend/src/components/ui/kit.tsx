/* The page kit shared by gardnr and listr -- the design language of gardnr's redesign
 * (claude.ai design "gardnr · Tuinen", Sept 2026), carried to listr: the design's own line
 * icons, its buttons and status chips, a page's top row and display title, and the dark
 * edit-mode bar. Colours are the `ui-*` tokens (index.css), which each of those modules defines
 * with its own brand colour -- never raw hex -- so dark mode and each module's accent follow. */
import ModuleIndicators from "../ModuleIndicators";
import type { ReactNode, SVGProps } from "react";

import ModuleSwitcher from "../ModuleSwitcher";

// -- Icons: the design's hand-drawn set, on a 24px grid ----------------------------------------

function Svg({ size = 20, strokeWidth = 2, children, ...rest }: { size?: number | string; strokeWidth?: number | string; children: ReactNode } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

type IconProps = { size?: number | string; strokeWidth?: number | string; className?: string };
export const IconChevronLeft = (p: IconProps) => <Svg {...p}><polyline points="15,18 9,12 15,6" /></Svg>;
export const IconChevronRight = (p: IconProps) => <Svg {...p}><polyline points="9,18 15,12 9,6" /></Svg>;
export const IconChevronUp = (p: IconProps) => <Svg {...p}><polyline points="6,15 12,9 18,15" /></Svg>;
export const IconChevronDown = (p: IconProps) => <Svg {...p}><polyline points="6,9 12,15 18,9" /></Svg>;
export const IconPencil = (p: IconProps) => <Svg {...p}><path d="M4 20 H8 L19 9 L15 5 L4 16 Z" /></Svg>;
export const IconCheck = (p: IconProps) => <Svg {...p}><polyline points="5,12 10,17 19,8" /></Svg>;
export const IconAlert = (p: IconProps) => (
  <Svg {...p}>
    <line x1="12" y1="7" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12" y2="17.01" />
  </Svg>
);
export const IconDroplet = (p: IconProps) => <Svg {...p}><path d="M12 3 C12 3 6 10 6 14.5 A6 6 0 0 0 18 14.5 C18 10 12 3 12 3 Z" /></Svg>;
export const IconTag = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 12 V4 H11 L21 14 L14 21 Z" />
    <circle cx="7.5" cy="8.5" r="1.2" />
  </Svg>
);
export const IconSquare = (p: IconProps) => <Svg {...p}><rect x="4" y="4" width="16" height="16" rx="3" /></Svg>;
export const IconSprout = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 21 V11" />
    <path d="M12 14 C7 14 5 11 5 7 C9 7 12 9.5 12 14 Z" />
    <path d="M12 11 C12 7 15 5 19 5 C19 9 16 11 12 11 Z" />
  </Svg>
);
export const IconTrash = (p: IconProps) => (
  <Svg {...p}>
    <polyline points="4,7 20,7" />
    <path d="M9 7 V4 H15 V7" />
    <path d="M6 7 L7 20 H17 L18 7" />
  </Svg>
);
export const IconGrip = (p: IconProps) => (
  <Svg {...p}>
    {[6, 12, 18].map((cy) => (
      <g key={cy}>
        <circle cx="9" cy={cy} r="1" />
        <circle cx="15" cy={cy} r="1" />
      </g>
    ))}
  </Svg>
);
export const IconPlus = (p: IconProps) => (
  <Svg {...p}>
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </Svg>
);
export const IconCalendarCheck = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="5" width="18" height="16" rx="3" />
    <line x1="3" y1="10" x2="21" y2="10" />
    <line x1="8" y1="3" x2="8" y2="7" />
    <line x1="16" y1="3" x2="16" y2="7" />
    <polyline points="9,15 11,17 15,13" />
  </Svg>
);
export const IconMap = (p: IconProps) => (
  <Svg {...p}>
    <polygon points="3,6 9,4 15,6 21,4 21,18 15,20 9,18 3,20" />
    <line x1="9" y1="4" x2="9" y2="18" />
    <line x1="15" y1="6" x2="15" y2="20" />
  </Svg>
);

// -- Buttons ----------------------------------------------------------------------------------

/** The design's secondary button: 44px, white, hairline border, 12px corners. */
export const secondaryButtonClass =
  "inline-flex h-11 items-center justify-center gap-1.5 rounded-xl border border-ui-border bg-ui-surface px-3.5 text-[15px] font-semibold text-ui-ink transition-colors hover:bg-ui-tile disabled:opacity-50";
/** The design's primary button: solid brand green. */
export const primaryButtonClass =
  "inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-ui-brand px-[18px] text-[15px] font-semibold text-white transition-colors hover:bg-ui-brand-strong disabled:opacity-50";
/** A 44px square icon button (reorder arrows); dims itself when disabled. */
export const iconButtonClass =
  "flex h-11 w-11 items-center justify-center rounded-xl border border-ui-border bg-ui-surface text-ui-ink disabled:bg-ui-tile disabled:text-ui-disabled";
/** Destructive outline button ("Verwijderen"). */
export const dangerButtonClass =
  "flex h-11 items-center gap-1.5 rounded-xl border border-ui-late-line bg-ui-surface px-3.5 text-sm font-semibold text-ui-late";
/** The dashed "+ Nieuwe tuin" call to action. */
export const dashedButtonClass =
  "flex h-14 items-center justify-center gap-2 rounded-[20px] border-2 border-dashed border-ui-line bg-transparent text-[15px] font-semibold text-ui-brand-strong hover:border-ui-brand";
export const inputClass =
  "h-11 w-full rounded-xl border border-ui-line bg-ui-surface px-3 text-base text-ui-ink focus:border-ui-brand focus:outline-none focus:ring-1 focus:ring-ui-brand";

// -- Status chips -------------------------------------------------------------------------------

export type DueState = "late" | "today";

const CHIP_STYLE = {
  late: "bg-ui-late-soft text-ui-late",
  today: "bg-ui-today-soft text-ui-today",
  ok: "bg-ui-brand-soft text-ui-brand-strong",
} as const;

/** "2 te laat" / "1 vandaag" / "Op schema" -- a 26px pill with the design's icon for each. */
export function StatusChip({ kind, children }: { kind: keyof typeof CHIP_STYLE; children: ReactNode }) {
  const Icon = kind === "late" ? IconAlert : kind === "today" ? IconDroplet : IconCheck;
  return (
    <span className={`inline-flex h-[26px] items-center gap-[5px] whitespace-nowrap rounded-full px-2.5 text-[13px] font-semibold ${CHIP_STYLE[kind]}`}>
      <Icon size={14} strokeWidth={2.4} />
      {children}
    </span>
  );
}

// -- Page top row -------------------------------------------------------------------------------

/** A page's top row (gardnr, listr): the module switcher pill on a phone (where the shared header is
 * hidden) or `left` in its place (a back link), and the page's actions on the right. */
export function ModuleTopRow({ left, children }: { left?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      {left ?? (
        <>
          <div className="flex items-center gap-1 sm:hidden">
            <ModuleSwitcher variant="pill" />
            <ModuleIndicators />
          </div>
          <span className="hidden sm:block" />
        </>
      )}
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

/** A page title in the design's display type, with an optional line underneath. */
export function PageTitle({ children, subtitle, size = "lg" }: { children: ReactNode; subtitle?: ReactNode; size?: "lg" | "md" }) {
  return (
    <div className="flex flex-col gap-1 pt-2">
      <h1 className={`m-0 font-display font-bold leading-[1.05] tracking-[-0.025em] text-ui-ink ${size === "lg" ? "text-4xl" : "text-[30px]"}`}>{children}</h1>
      {subtitle && <p className="m-0 text-[15px] text-ui-ink-soft">{subtitle}</p>}
    </div>
  );
}

// -- Edit mode bar ------------------------------------------------------------------------------

/** The dark bar that replaces a page's header while it's being edited: a small caps "Bewerken"
 * over what's being edited, and a white "Klaar". Runs edge to edge on a phone (cancelling the
 * page's own padding), a rounded bar on wider screens. */
export function EditBar({ title, onDone }: { title: string; onDone: () => void }) {
  return (
    <div className="-mx-4 -mt-4 flex items-center justify-between bg-ui-edit-bar px-4 py-3 text-white sm:mx-0 sm:mt-0 sm:rounded-2xl">
      <div className="flex min-w-0 flex-col gap-px">
        <span className="text-xs font-semibold uppercase tracking-[0.06em] text-ui-edit-bar-label">Bewerken</span>
        <span className="truncate font-display text-xl font-bold tracking-[-0.02em]">{title}</span>
      </div>
      <button
        type="button"
        onClick={onDone}
        className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-[18px] text-[15px] font-semibold text-[#1B1A1F]"
      >
        <IconCheck size={18} />
        Klaar
      </button>
    </div>
  );
}
