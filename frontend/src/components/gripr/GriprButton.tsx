import type { ButtonHTMLAttributes } from "react";

type Variant = "filled" | "tonal" | "outlined" | "text";

// Four button styles, by how much visual weight they carry: filled for a screen's one primary
// action, tonal for a secondary action that still deserves a fill, outlined/text for anything
// lower-emphasis than that. Shaped like the page kit's buttons (components/ui/kit.tsx): 44px,
// 12px corners -- the Material roles they're coloured with map onto the kit's tokens.
const VARIANT_CLASSES: Record<Variant, string> = {
  filled: "bg-primary text-on-primary hover:bg-on-primary-container",
  tonal: "bg-secondary-container text-on-secondary-container hover:opacity-90",
  outlined: "border border-outline-variant bg-surface text-on-surface hover:bg-surface-container",
  text: "text-primary hover:bg-primary/10",
};

export default function GriprButton({
  variant = "filled",
  className = "",
  ...props
}: { variant?: Variant } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex h-11 items-center justify-center gap-1.5 rounded-xl px-[18px] text-[15px] font-semibold transition-colors disabled:opacity-40 ${VARIANT_CLASSES[variant]} ${className}`}
    />
  );
}
