import { useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import CollapsibleCard from "./CollapsibleCard";
import type { Position } from "../api/types";
import { useTheme } from "../hooks/useTheme";
import { formatEur, formatWeight, toNumber } from "../utils/format";
import { CATEGORICAL_COLORS as SLICE_COLORS, OTHER_COLOR } from "../utils/palette";

// Beyond these fixed slots, the long tail folds into a single neutral "Other" slice rather
// than inventing more hues: a generated 9th hue is indistinguishable from an existing one for
// a colourblind reader, and a 15-wedge donut is unreadable regardless. Clicking "Other" drills
// into just that tail (see `showingOther` below), where the same 8-colour cap applies again —
// so a tail of 8 or fewer gets full colour, and a longer one folds the same way one level down.
const MAX_SLICES = SLICE_COLORS.length;

interface RawEntry {
  name: string;
  value: number;
  weight: number;
}

interface Entry extends RawEntry {
  color: string;
}

/** Every position, largest first, uncoloured — colour depends on which slice of this list is
 * actually on screen (the whole portfolio, or a drilled-into "Other" tail), so it's assigned
 * separately by `assignColors`. */
function sortedPositions(positions: Position[]): RawEntry[] {
  return positions
    .map((p) => ({
      name: p.ticker === "CASH" ? "Cash" : p.ticker,
      value: toNumber(p.market_value_eur) ?? 0,
      weight: toNumber(p.weight_pct) ?? 0,
    }))
    .filter((s) => s.value > 0)
    .sort((a, b) => b.value - a.value);
}

/** The first `MAX_SLICES` get a real, colourblind-checked hue in rank order; everything after
 * that shares the neutral "Other" colour — so a row in the table always points at something
 * visible in the donut, and the same rule applies whether this list is the whole portfolio or
 * a drilled-into tail. */
function assignColors(entries: RawEntry[]): Entry[] {
  return entries.map((s, i) => ({ ...s, color: i < MAX_SLICES ? SLICE_COLORS[i] : OTHER_COLOR }));
}

function buildWedges(entries: Entry[]): (Entry & { isOther?: boolean })[] {
  const head = entries.slice(0, MAX_SLICES);
  const tail = entries.slice(MAX_SLICES);
  if (!tail.length) return head;
  return [
    ...head,
    {
      name: `Other (${tail.length})`,
      value: tail.reduce((sum, s) => sum + s.value, 0),
      weight: tail.reduce((sum, s) => sum + s.weight, 0),
      color: OTHER_COLOR,
      isOther: true,
    },
  ];
}

function SliceTooltip({ active, payload }: { active?: boolean; payload?: { payload: Entry }[] }) {
  if (!active || !payload?.length) return null;
  const slice = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
      <div className="flex items-center gap-2">
        <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: slice.color }} />
        <span className="font-medium text-slate-900">{slice.name}</span>
      </div>
      <div className="mt-0.5 tabular-nums text-slate-600">
        {formatEur(slice.value)} · {formatWeight(slice.weight)}
      </div>
    </div>
  );
}

export default function AllocationPieChart({
  positions,
  isLoading,
}: {
  positions: Position[] | undefined;
  isLoading: boolean;
}) {
  const { isDark } = useTheme();
  const [showingOther, setShowingOther] = useState(false);

  const raw = positions ? sortedPositions(positions) : [];
  const tailRaw = raw.slice(MAX_SLICES);

  // If the tail that was drilled into shrinks away entirely (a sale, a price move that pulls a
  // position back into the top 8), silently drilling back out beats leaving an empty donut.
  useEffect(() => {
    if (showingOther && tailRaw.length === 0) setShowingOther(false);
     
  }, [showingOther, tailRaw.length]);

  const entries = assignColors(showingOther ? tailRaw : raw);
  const wedges = buildWedges(entries);
  const groupedFrom = entries.length > MAX_SLICES ? MAX_SLICES : -1;
  // The gap between wedges is a stroke matching the card surface behind the donut, not
  // literally white — it needs to switch with the surface, which is a CSS override in dark mode.
  const wedgeGapColor = isDark ? "#1e293b" : "#ffffff";

  return (
    <CollapsibleCard
      storageKey="allocation-chart"
      title="Allocation"
      meta={
        showingOther && (
          <button
            type="button"
            onClick={() => setShowingOther(false)}
            className="text-xs font-medium text-blue-600 hover:underline"
          >
            ← All positions
          </button>
        )
      }
    >
      {isLoading ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">Loading…</div>
      ) : entries.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">No positions to show</div>
      ) : (
        <div className="mt-2 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
          <div className="h-64 w-full sm:w-1/2">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={wedges}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="55%"
                  outerRadius="85%"
                  paddingAngle={1}
                  stroke={wedgeGapColor}
                  strokeWidth={2}
                  isAnimationActive={false}
                >
                  {wedges.map((slice) => (
                    <Cell
                      key={slice.name}
                      fill={slice.color}
                      cursor={slice.isOther ? "pointer" : undefined}
                      onClick={slice.isOther ? () => setShowingOther(true) : undefined}
                    />
                  ))}
                </Pie>
                <Tooltip content={<SliceTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Every position, not just the ones that earned a wedge. This doubles as the
              accessible read-out — each holding is named and valued, so identity never rests
              on colour alone — and as the relief for slice hues that sit under 3:1 against
              the card surface. It runs to full length rather than scrolling inside a fixed
              box: a cut-off row reads as broken, and the whole card folds away if it's long. */}
          <ul className="w-full space-y-1 text-sm sm:w-1/2">
            {entries.map((entry, i) => (
              <li key={entry.name}>
                {i === groupedFrom &&
                  (showingOther ? (
                    <div className="mb-1 mt-2 border-t border-slate-100 pt-2 text-xs text-slate-400">
                      grouped into Other
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setShowingOther(true)}
                      className="mb-1 mt-2 flex w-full items-center gap-1 border-t border-slate-100 pt-2 text-left text-xs text-slate-400 hover:text-blue-600 hover:underline"
                    >
                      grouped into Other · click to view
                    </button>
                  ))}
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="truncate text-slate-700">{entry.name}</span>
                  <span className="ml-auto shrink-0 tabular-nums text-slate-500">{formatWeight(entry.weight)}</span>
                  <span className="w-24 shrink-0 text-right tabular-nums text-slate-400">{formatEur(entry.value)}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </CollapsibleCard>
  );
}
