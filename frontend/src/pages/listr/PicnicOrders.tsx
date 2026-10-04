import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { listrApi } from "../../api/listrClient";
import type { ListrPicnicMonth } from "../../api/listrTypes";
import PicnicConnectCard from "../../components/listr/PicnicConnectCard";
import PicnicSyncCard from "../../components/listr/PicnicSyncCard";
import { IconChevronLeft, ModuleTopRow, PageTitle, secondaryButtonClass } from "../../components/ui/kit";
import { usePicnicConnect } from "../../hooks/usePicnicConnect";
import { formatEur, toNumber } from "../../utils/format";

const dayLabel = (iso: string) =>
  new Date(iso).toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const sinceLabel = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });
const monthLabel = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("nl-NL", { month: "short" });
const monthLongLabel = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("nl-NL", { month: "long", year: "numeric" });

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl bg-ui-tile p-3">
      <div className="text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{label}</div>
      <div className="mt-1 font-display text-xl font-bold tabular-nums tracking-[-0.02em] text-ui-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs font-medium text-ui-muted">{sub}</div>}
    </div>
  );
}

function ProcessedChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex h-[22px] items-center rounded-full bg-ui-brand-soft px-2 text-[12px] font-semibold text-ui-brand-strong">
      {children}
    </span>
  );
}

type MonthRow = { month: string; label: string; total: number; deliveries: number; partial: boolean };

function MonthTooltip({ active, payload }: { active?: boolean; payload?: { payload: MonthRow }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-xl border border-ui-border bg-ui-surface px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold text-ui-ink first-letter:uppercase">{monthLongLabel(row.month)}</div>
      <div className="mt-0.5 tabular-nums text-ui-ink">{formatEur(row.total)}</div>
      <div className="text-ui-muted">
        {row.deliveries} {row.deliveries === 1 ? "levering" : "leveringen"}
        {row.partial && " · deel van de maand"}
      </div>
    </div>
  );
}

/** Spending per calendar month. The window is a rolling 12 months, so the first and the current
 * month only cover part of a month -- those bars are drawn lighter, and the note says why, so a
 * half-finished month doesn't read as a drop in spending. */
function MonthlyChart({ months }: { months: ListrPicnicMonth[] }) {
  const rows: MonthRow[] = months.map((m, i) => ({
    month: m.month,
    label: monthLabel(m.month),
    total: toNumber(m.total) ?? 0,
    deliveries: m.deliveries,
    partial: i === 0 || i === months.length - 1,
  }));
  return (
    <div className="kit-bars flex flex-col gap-2">
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} interval={0} tick={{ fontSize: 11 }} />
            <YAxis
              width={44}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => formatEur(v, true)}
            />
            <Tooltip content={<MonthTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
            <Bar dataKey="total" radius={[4, 4, 0, 0]} maxBarSize={28}>
              {rows.map((r) => (
                <Cell key={r.month} fillOpacity={r.partial ? 0.4 : 1} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="m-0 text-xs text-ui-muted">De lichte maanden vallen maar deels binnen de 12 maanden.</p>
    </div>
  );
}

/** listr's view of the Picnic account's order history: what was spent over the last 12
 * months, per month and per delivery. Read live from Picnic each visit (see
 * listr_picnic_service.order_history); nothing is stored. Amounts are the groceries after
 * discounts, excluding deposit (statiegeld). */
export default function ListrPicnicOrders() {
  const queryClient = useQueryClient();
  const picnic = usePicnicConnect(() => queryClient.invalidateQueries({ queryKey: ["listr-picnic-orders"] }));
  const connected = picnic.status?.connected ?? false;

  const ordersQuery = useQuery({
    queryKey: ["listr-picnic-orders"],
    queryFn: () => listrApi.picnicOrders(),
    enabled: connected,
    retry: false,
  });
  // A session that expired since the status check comes back as 409 -- refresh the status so
  // the page offers to reconnect instead of showing a dead error.
  const expired = ordersQuery.error instanceof Error && ordersQuery.error.message.startsWith("409");
  useEffect(() => {
    if (expired) queryClient.invalidateQueries({ queryKey: ["listr-picnic-status"] });
  }, [expired, queryClient]);

  const data = ordersQuery.data;

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow
        left={
          <Link to="/listr" aria-label="Terug naar lijsten" className={`${secondaryButtonClass} pl-2 pr-3 no-underline`}>
            <IconChevronLeft size={20} />
            Lijsten
          </Link>
        }
      >
        <Link to="/listr/winkelwagen" aria-label="Picnic-winkelwagen" className={`${secondaryButtonClass} no-underline`}>
          <ShoppingCart className="h-[18px] w-[18px]" strokeWidth={2} />
          <span className="hidden sm:inline">Winkelwagen</span>
        </Link>
      </ModuleTopRow>
      <PageTitle subtitle={data ? `Afgelopen 12 maanden, sinds ${sinceLabel(data.since)}` : "Afgelopen 12 maanden"}>
        Picnic-bestellingen
      </PageTitle>

      {!picnic.status ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>
      ) : !picnic.status.configured || !connected ? (
        <PicnicConnectCard picnic={picnic} reason="Verbind met Picnic om je bestellingen en uitgaven te zien." />
      ) : ordersQuery.isLoading ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">
          Bestellingen ophalen bij Picnic…
        </div>
      ) : ordersQuery.isError || !data ? (
        <div className="rounded-2xl bg-ui-late-soft px-4 py-3.5 text-[15px] font-semibold text-ui-late">
          Picnic-bestellingen ophalen is mislukt. Probeer het later opnieuw.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat label="Uitgegeven" value={formatEur(data.total)} sub="excl. statiegeld" />
            <Stat
              label="Leveringen"
              value={String(data.deliveries.length)}
              sub={`${data.deliveries.reduce((n, d) => n + d.order_count, 0)} bestellingen`}
            />
            <Stat label="Per levering" value={formatEur(data.average_per_delivery)} sub="gemiddeld" />
          </div>

          {data.deliveries.length === 0 ? (
            <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">
              Geen Picnic-leveringen in de afgelopen 12 maanden.
            </div>
          ) : (
            <>
              <section className="flex flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface p-4">
                <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Per maand</h2>
                <MonthlyChart months={data.months} />
              </section>

              <PicnicSyncCard />

              <section className="overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
                <h2 className="m-0 border-b border-ui-border px-4 py-3 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">
                  Leveringen
                </h2>
                <ul className="m-0 list-none divide-y divide-ui-border p-0">
                  {data.deliveries.map((d) => (
                    <li key={d.id} className="flex min-h-[52px] items-center justify-between gap-3 px-4 py-2">
                      <div className="flex min-w-0 flex-col">
                        <span className="block text-[15px] font-medium text-ui-ink first-letter:uppercase">{dayLabel(d.delivered_at)}</span>
                        <span className="text-xs text-ui-muted">
                          {d.order_count} {d.order_count === 1 ? "bestelling" : "bestellingen"}
                        </span>
                        {d.processed && (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {d.processed.orders_booked > 0 && <ProcessedChip>in gripr geboekt</ProcessedChip>}
                            {d.processed.orders_matched > 0 && <ProcessedChip>al geboekt</ProcessedChip>}
                            {d.processed.items_restocked > 0 && <ProcessedChip>+{d.processed.items_restocked} voorraad</ProcessedChip>}
                          </span>
                        )}
                      </div>
                      <span className="shrink-0 text-[15px] font-semibold tabular-nums text-ui-ink">{formatEur(d.total)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
