import { Plus } from "lucide-react";

/** A page's one primary "add" action as a floating button on mobile, sitting just above the
 * page kit's bottom bar in the thumb zone, in the module's brand colour. Callers hide their
 * header button below `sm` (`hidden sm:inline-block`) so exactly one of the two is visible.
 *
 * Rendered after the page's content, it also leaves a button-high gap there, so the last row of
 * a list can scroll up out from under the button instead of staying hidden behind it. */
export default function MobileFab({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <>
      <div aria-hidden data-testid="fab-spacer" className="h-16 sm:hidden" />
      <button
        type="button"
        onClick={onClick}
        className="fixed bottom-24 right-4 z-30 flex h-14 items-center gap-2 rounded-2xl bg-ui-brand px-5 text-[15px] font-semibold text-white shadow-lg hover:bg-ui-brand-strong sm:hidden"
      >
        <Plus className="h-5 w-5" strokeWidth={2.4} />
        {label}
      </button>
    </>
  );
}
