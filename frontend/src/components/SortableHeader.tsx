import type { SortState } from "../hooks/useTableSort";

/** A column header that sorts the table it belongs to. Renders as a real <button> inside the
 * <th> so it's keyboard-reachable, and carries aria-sort so a screen reader announces the
 * current order rather than leaving it to the arrow glyph. */
export default function SortableHeader<K extends string>({
  label,
  sortKey,
  sort,
  onToggle,
  align = "left",
  className = "",
}: {
  label: string;
  sortKey: K;
  sort: SortState<K>;
  onToggle: (key: K) => void;
  align?: "left" | "right";
  className?: string;
}) {
  const active = sort.key === sortKey;
  const ariaSort = active ? (sort.direction === "asc" ? "ascending" : "descending") : "none";

  return (
    <th
      className={`px-4 py-2 font-medium ${align === "right" ? "text-right" : "text-left"} ${className}`}
      aria-sort={ariaSort}
    >
      <button
        type="button"
        onClick={() => onToggle(sortKey)}
        className={`inline-flex items-center gap-1 uppercase tracking-wide transition-colors hover:text-slate-700 ${
          align === "right" ? "flex-row-reverse" : ""
        } ${active ? "text-slate-700" : ""}`}
      >
        <span>{label}</span>
        <span aria-hidden className={active ? "text-slate-400" : "text-transparent"}>
          {active && sort.direction === "asc" ? "▲" : "▼"}
        </span>
      </button>
    </th>
  );
}
