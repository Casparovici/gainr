import { ChevronDown, ChevronRight } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { InfoButton } from "./InfoTip";

const TONES = {
  gripr: { title: "text-on-surface-variant hover:text-on-surface", info: "text-on-surface-variant hover:text-on-surface", text: "text-xs text-on-surface-variant", rule: "border-outline-variant" },
  gainr: { title: "text-slate-500 hover:text-slate-800", info: "text-slate-400 hover:text-slate-600", text: "text-sm text-slate-600", rule: "border-slate-200" },
} as const;

/** A settings section that starts folded: only its title shows, and tapping the title opens it. The
 * row also holds what's useful without opening it -- an ⓘ with the explanation, a status, and
 * `actions` such as a sync icon. `open` makes it controlled, for a section that opens itself when
 * something in it needs attention. */
export default function SettingsSection({
  title,
  info,
  infoLabel,
  meta,
  actions,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  tone = "gripr",
  children,
}: {
  title: string;
  info?: ReactNode;
  infoLabel?: string;
  meta?: ReactNode;
  actions?: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  tone?: keyof typeof TONES;
  children: ReactNode;
}) {
  const [ownOpen, setOwnOpen] = useState(defaultOpen);
  const [infoOpen, setInfoOpen] = useState(false);
  const bodyId = useId();
  const infoId = useId();
  const open = controlledOpen ?? ownOpen;
  const toggle = () => {
    onOpenChange?.(!open);
    setOwnOpen(!open);
  };
  const t = TONES[tone];

  return (
    <section aria-label={title} className={`flex flex-col gap-2 border-t pt-3 first:border-t-0 first:pt-0 ${t.rule}`}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={bodyId}
          className={`flex min-w-0 flex-1 items-center gap-1.5 text-left ${t.title}`}
        >
          {open ? <ChevronDown className="h-4 w-4 shrink-0" aria-hidden /> : <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />}
          <span className="text-sm font-semibold uppercase tracking-wide">{title}</span>
        </button>
        {meta}
        {info && <InfoButton label={infoLabel ?? title} open={infoOpen} onToggle={() => setInfoOpen((v) => !v)} controls={infoId} className={t.info} />}
        {actions}
      </div>
      {info && (
        <p id={infoId} hidden={!infoOpen} className={t.text}>
          {info}
        </p>
      )}
      <div id={bodyId} hidden={!open} className="flex flex-col gap-2">
        {open && children}
      </div>
    </section>
  );
}
