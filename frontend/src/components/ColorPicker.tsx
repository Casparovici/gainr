import { useEffect, useRef, useState } from "react";

import { PICKER_COLORS } from "../utils/palette";

/** A small swatch popover for overriding a colour. Wraps whatever badge/trigger is passed in;
 * clicking a swatch picks it and closes, the × resets to the derived default (or `null`, for a
 * caller with no such concept). Closes on an outside click rather than on mouse-leave — the
 * popover sits a few pixels below the trigger (`top-full` plus a margin), a gap the wrapping
 * `relative` box doesn't cover since an absolutely-positioned child doesn't extend its parent's
 * own box, so hovering from the trigger down into the swatches used to cross that gap and fire
 * mouseleave before the click ever landed. */
export default function ColorPicker({
  value,
  onSelect,
  trigger,
}: {
  value: string | null;
  onSelect: (color: string | null) => void;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        title="Change colour"
      >
        {trigger}
      </button>
      {open && (
        // Stops a swatch pick from also bubbling up to whatever the trigger sits inside — e.g.
        // an account card whose own onClick opens a detail dialog.
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute left-0 top-full z-20 mt-1 flex w-36 flex-wrap gap-1.5 rounded-lg border border-slate-200 bg-white p-2 shadow-lg"
        >
          {PICKER_COLORS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => {
                onSelect(c);
                setOpen(false);
              }}
              className="h-6 w-6 rounded-full hover:ring-2 hover:ring-offset-1 hover:ring-slate-400"
              style={{ backgroundColor: c, boxShadow: value === c ? "0 0 0 2px white, 0 0 0 3.5px #0f172a" : undefined }}
              title={c}
            />
          ))}
          <button
            type="button"
            onClick={() => {
              onSelect(null);
              setOpen(false);
            }}
            className="flex h-6 w-6 items-center justify-center rounded-full border border-slate-300 text-xs text-slate-400 hover:bg-slate-50"
            title="Reset to default"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
