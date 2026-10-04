import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus, ReceiptEuro, ShoppingCart, Tag } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import type { ListrPicnicCart, ListrPicnicSlot } from "../../api/listrTypes";
import PicnicConnectCard from "../../components/listr/PicnicConnectCard";
import PicnicThumb from "../../components/listr/PicnicThumb";
import ModalOverlay from "../../components/ModalOverlay";
import { IconChevronLeft, ModuleTopRow, PageTitle, primaryButtonClass, secondaryButtonClass } from "../../components/ui/kit";
import { usePicnicConnect } from "../../hooks/usePicnicConnect";
import { formatEur, toNumber } from "../../utils/format";

// An order whose payment is underway, remembered across the trip to the bank and back (the bank
// returns to this page). Per-device convenience only -- Picnic itself is the record.
const PENDING_KEY = "listr.picnic.pendingCheckout";
type PendingCheckout = { transactionId: string; paymentUrl: string; slotLabel: string; total: string; startedAt: number };
const PENDING_TTL_MS = 60 * 60 * 1000;

function readPending(): PendingCheckout | null {
  try {
    const raw = localStorage.getItem(PENDING_KEY);
    if (!raw) return null;
    const pending = JSON.parse(raw) as PendingCheckout;
    return Date.now() - pending.startedAt < PENDING_TTL_MS ? pending : null;
  } catch {
    return null;
  }
}
function writePending(pending: PendingCheckout | null) {
  try {
    if (pending) localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
    else localStorage.removeItem(PENDING_KEY);
  } catch {
    // Private window / blocked storage: the flow still works within this page view.
  }
}

const dayKey = (iso: string) => iso.slice(0, 10);
const dayLabel = (iso: string) =>
  new Date(iso).toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
const time = (iso: string) => new Date(iso).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
const slotLabel = (slot: ListrPicnicSlot) => `${dayLabel(slot.window_start)} ${time(slot.window_start)}–${time(slot.window_end)}`;
const cutOffLabel = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { weekday: "short", hour: "2-digit", minute: "2-digit" });

function CartLines({ cart, onAdd, onRemove, busy }: { cart: ListrPicnicCart; onAdd: (id: string) => void; onRemove: (id: string) => void; busy: boolean }) {
  return (
    <ul className="m-0 list-none divide-y divide-ui-border p-0">
      {cart.lines.map((line) => (
        <li key={line.product_id} className="flex min-h-[60px] items-center gap-3 px-4 py-2">
          <PicnicThumb url={line.image_url} size={44} />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-[15px] text-ui-ink">{line.name}</span>
            <span className="text-xs text-ui-muted">
              {line.unit_quantity} · <span className="font-semibold text-ui-ink-soft">{formatEur(line.price)}</span>
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => onRemove(line.product_id)}
              disabled={busy}
              aria-label={`Een ${line.name} minder`}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-ui-line bg-ui-surface text-ui-ink-soft hover:bg-ui-tile disabled:opacity-40"
            >
              <Minus className="h-4 w-4" strokeWidth={2} />
            </button>
            <span className="w-6 text-center text-[15px] font-semibold tabular-nums text-ui-ink">{line.count}</span>
            <button
              type="button"
              onClick={() => onAdd(line.product_id)}
              disabled={busy}
              aria-label={`Een ${line.name} meer`}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-ui-line bg-ui-surface text-ui-ink-soft hover:bg-ui-tile disabled:opacity-40"
            >
              <Plus className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Choosing when Picnic delivers: a day, then one of its windows. Full and closed windows stay
 * visible (greyed) so the reader sees why a time isn't offered; picking one calls Picnic right
 * away, the same as in its own app. */
function SlotPicker({
  slots,
  selectedId,
  chosen,
  onPick,
  busy,
}: {
  slots: ListrPicnicSlot[];
  selectedId: string | null;
  chosen: boolean;
  onPick: (slot: ListrPicnicSlot) => void;
  busy: boolean;
}) {
  const days = useMemo(() => {
    const byDay = new Map<string, ListrPicnicSlot[]>();
    for (const slot of slots) {
      const key = dayKey(slot.window_start);
      byDay.set(key, [...(byDay.get(key) ?? []), slot]);
    }
    return [...byDay.entries()].map(([key, daySlots]) => ({ key, slots: daySlots, open: daySlots.some((s) => s.is_available) }));
  }, [slots]);
  const selected = slots.find((s) => s.id === selectedId) ?? null;
  const [day, setDay] = useState<string | null>(null);
  const activeDay = day ?? (selected ? dayKey(selected.window_start) : days.find((d) => d.open)?.key ?? null);
  const daySlots = days.find((d) => d.key === activeDay)?.slots ?? [];

  return (
    <div className="flex flex-col gap-3">
      <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none]">
        {days.map((d) => (
          <button
            key={d.key}
            type="button"
            onClick={() => setDay(d.key)}
            disabled={!d.open}
            aria-pressed={d.key === activeDay}
            className={`flex h-9 shrink-0 items-center rounded-full border px-3.5 text-sm font-semibold disabled:opacity-40 ${
              d.key === activeDay
                ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong"
                : "border-ui-border bg-ui-surface text-ui-ink-soft hover:border-ui-line"
            }`}
          >
            {dayLabel(d.slots[0].window_start)}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {daySlots.map((slot) => {
          const isSelected = slot.id === selectedId;
          return (
            <button
              key={slot.id}
              type="button"
              onClick={() => onPick(slot)}
              disabled={!slot.is_available || busy}
              aria-pressed={isSelected}
              className={`flex min-h-[52px] flex-col items-center justify-center rounded-xl border px-2 py-1.5 text-center disabled:cursor-not-allowed disabled:opacity-40 ${
                isSelected
                  ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong"
                  : "border-ui-border bg-ui-surface text-ui-ink hover:border-ui-line"
              }`}
            >
              <span className="text-[15px] font-semibold tabular-nums">
                {time(slot.window_start)}–{time(slot.window_end)}
              </span>
              <span className="text-[11px] text-ui-muted">
                {!slot.is_available ? (slot.unavailable_reason === "OUT_OF_CAPACITY" ? "vol" : "niet beschikbaar") : slot.minimum_order ? `min. ${formatEur(slot.minimum_order)}` : " "}
              </span>
            </button>
          );
        })}
      </div>
      {selected && (
        <p className="m-0 text-sm text-ui-ink-soft">
          {chosen ? "Gekozen" : "Voorgesteld door Picnic"}: <span className="font-semibold text-ui-ink">{slotLabel(selected)}</span> · bestellen
          vóór {cutOffLabel(selected.cut_off)}
        </p>
      )}
    </div>
  );
}

/** listr's view of the live Picnic cart: adjust quantities, choose when it's delivered, and
 * order. Ordering starts Picnic's checkout and sends the reader to their bank (iDEAL); the
 * order is placed only once they approve the payment there -- nothing in listr itself can spend
 * money. See docs/adr/0028-picnic-ordering-from-listr.md. */
export default function ListrPicnicCart() {
  const queryClient = useQueryClient();
  const picnic = usePicnicConnect(() => queryClient.invalidateQueries({ queryKey: ["listr-picnic-cart"] }));
  const connected = picnic.status?.connected ?? false;
  const [pending, setPending] = useState<PendingCheckout | null>(() => readPending());
  const [confirming, setConfirming] = useState(false);
  const [placed, setPlaced] = useState<PendingCheckout | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cartQuery = useQuery({ queryKey: ["listr-picnic-cart"], queryFn: () => listrApi.picnicCart(), enabled: connected, retry: false });
  const slotsQuery = useQuery({ queryKey: ["listr-picnic-slots"], queryFn: () => listrApi.picnicSlots(), enabled: connected, retry: false });
  const cart = cartQuery.data;

  const expired = [cartQuery.error, slotsQuery.error].some((e) => e instanceof Error && e.message.startsWith("409"));
  useEffect(() => {
    if (expired) queryClient.invalidateQueries({ queryKey: ["listr-picnic-status"] });
  }, [expired, queryClient]);

  const setCart = (next: ListrPicnicCart) => queryClient.setQueryData(["listr-picnic-cart"], next);
  const addMutation = useMutation({ mutationFn: (id: string) => listrApi.picnicCartAdd(id), onSuccess: setCart });
  const removeMutation = useMutation({ mutationFn: (id: string) => listrApi.picnicCartRemove(id), onSuccess: setCart });
  const slotMutation = useMutation({
    mutationFn: (slot: ListrPicnicSlot) => listrApi.setPicnicSlot(slot.id),
    onSuccess: (next) => {
      setCart(next);
      queryClient.invalidateQueries({ queryKey: ["listr-picnic-slots"] });
    },
  });

  const slots = slotsQuery.data ?? [];
  const selectedSlot = slots.find((s) => s.id === cart?.selected_slot_id) ?? null;
  const belowMinimum =
    !!selectedSlot?.minimum_order && (toNumber(cart?.total ?? null) ?? 0) < (toNumber(selectedSlot.minimum_order) ?? 0);
  const canOrder = !!cart && cart.lines.length > 0 && !!selectedSlot && selectedSlot.is_available && cart.slot_chosen && !belowMinimum;

  const checkoutMutation = useMutation({
    mutationFn: () => listrApi.picnicCheckout(cart!.mts, `${window.location.origin}/listr/winkelwagen`),
    onSuccess: (checkout) => {
      const next: PendingCheckout = {
        transactionId: checkout.transaction_id,
        paymentUrl: checkout.payment_url,
        slotLabel: selectedSlot ? slotLabel(selectedSlot) : "",
        total: cart!.checkout_total,
        // In the mutation's success callback, not during render; the rule can't tell the two apart.
        // eslint-disable-next-line react-hooks/purity
        startedAt: Date.now(),
      };
      writePending(next);
      setPending(next);
      setConfirming(false);
      window.location.assign(checkout.payment_url);
    },
    onError: (e) => {
      setConfirming(false);
      setError(e instanceof Error && e.message.startsWith("400") ? e.message.replace(/^400[^:]*: /, "") : "Bestellen is mislukt. Probeer het opnieuw.");
      queryClient.invalidateQueries({ queryKey: ["listr-picnic-cart"] });
    },
  });

  // While a payment is underway: ask Picnic every few seconds whether it went through.
  const statusQuery = useQuery({
    queryKey: ["listr-picnic-checkout", pending?.transactionId],
    queryFn: () => listrApi.picnicCheckoutStatus(pending!.transactionId),
    enabled: connected && !!pending,
    refetchInterval: 3000,
  });
  useEffect(() => {
    if (statusQuery.data?.finished && pending) {
      setPlaced(pending);
      writePending(null);
      setPending(null);
      queryClient.invalidateQueries({ queryKey: ["listr-picnic-cart"] });
      queryClient.invalidateQueries({ queryKey: ["listr-picnic-slots"] });
      queryClient.invalidateQueries({ queryKey: ["listr-picnic-orders"] });
    }
  }, [statusQuery.data, pending, queryClient]);

  const cancelMutation = useMutation({
    mutationFn: () => listrApi.cancelPicnicCheckout(pending!.transactionId),
    onSettled: () => {
      writePending(null);
      setPending(null);
      queryClient.invalidateQueries({ queryKey: ["listr-picnic-cart"] });
    },
  });

  const busy = addMutation.isPending || removeMutation.isPending;

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
        <Link to="/listr/aanbiedingen" aria-label="Aanbiedingen" className={`${secondaryButtonClass} no-underline`}>
          <Tag className="h-[18px] w-[18px]" strokeWidth={2} />
          Aanbiedingen
        </Link>
        <Link to="/listr/bestellingen" aria-label="Picnic-bestellingen" className={`${secondaryButtonClass} no-underline`}>
          <ReceiptEuro className="h-[18px] w-[18px]" strokeWidth={2} />
          <span className="hidden sm:inline">Bestellingen</span>
        </Link>
      </ModuleTopRow>
      <PageTitle subtitle={cart ? `${cart.item_count} ${cart.item_count === 1 ? "product" : "producten"} · ${formatEur(cart.checkout_total)}` : "Je Picnic-winkelwagen"}>
        Winkelwagen
      </PageTitle>

      {placed && (
        <div className="rounded-2xl bg-ui-brand-soft px-4 py-3.5 text-ui-brand-strong">
          <div className="text-[15px] font-bold">Besteld bij Picnic</div>
          <div className="text-sm">
            {placed.slotLabel} · {formatEur(placed.total)}. Je ziet hem bij <Link to="/listr/bestellingen" className="font-semibold underline">Bestellingen</Link> zodra hij bezorgd is.
          </div>
        </div>
      )}

      {pending && (
        <div className="flex flex-col gap-3 rounded-2xl bg-ui-today-soft px-4 py-3.5 text-ui-today">
          <div>
            <div className="text-[15px] font-bold">Betaling bezig</div>
            <div className="text-sm">
              Rond de betaling van {formatEur(pending.total)} af in je bank-app. Pas daarna is de bestelling voor {pending.slotLabel} geplaatst.
              {statusQuery.data && !statusQuery.data.finished && ` (status: ${statusQuery.data.status.toLowerCase()})`}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <a href={pending.paymentUrl} className={`${primaryButtonClass} h-11 no-underline`}>
              Naar betalen
            </a>
            <button type="button" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending} className={secondaryButtonClass}>
              {cancelMutation.isPending ? "Annuleren…" : "Bestelling annuleren"}
            </button>
          </div>
        </div>
      )}

      {!picnic.status ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>
      ) : !picnic.status.configured || !connected ? (
        <PicnicConnectCard picnic={picnic} reason="Verbind met Picnic om je winkelwagen te zien en te bestellen." />
      ) : cartQuery.isLoading ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Winkelwagen ophalen bij Picnic…</div>
      ) : cartQuery.isError || !cart ? (
        <div className="rounded-2xl bg-ui-late-soft px-4 py-3.5 text-[15px] font-semibold text-ui-late">De winkelwagen ophalen is mislukt. Probeer het later opnieuw.</div>
      ) : cart.lines.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted">
          <ShoppingCart className="h-8 w-8 text-ui-faint" strokeWidth={1.5} />
          Je Picnic-winkelwagen is leeg. Open een lijst en kies "Push naar Picnic" om hem te vullen, of kijk bij de{" "}
          <Link to="/listr/aanbiedingen" className="font-semibold text-ui-brand-strong">
            aanbiedingen
          </Link>
          .
        </div>
      ) : (
        <>
          <section className="overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
            <CartLines cart={cart} onAdd={(id) => addMutation.mutate(id)} onRemove={(id) => removeMutation.mutate(id)} busy={busy} />
            <dl className="m-0 flex flex-col gap-1 border-t border-ui-border px-4 py-3 text-sm">
              <div className="flex justify-between text-ui-ink-soft">
                <dt>Producten</dt>
                <dd className="m-0 tabular-nums">{formatEur(cart.total)}</dd>
              </div>
              {toNumber(cart.deposit) ? (
                <div className="flex justify-between text-ui-ink-soft">
                  <dt>Statiegeld</dt>
                  <dd className="m-0 tabular-nums">{formatEur(cart.deposit)}</dd>
                </div>
              ) : null}
              <div className="flex justify-between text-[15px] font-bold text-ui-ink">
                <dt>Te betalen</dt>
                <dd className="m-0 tabular-nums">{formatEur(cart.checkout_total)}</dd>
              </div>
            </dl>
          </section>

          <section className="flex flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface p-4">
            <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Bezorgmoment</h2>
            {slotsQuery.isLoading ? (
              <p className="m-0 text-sm text-ui-muted">Tijden ophalen…</p>
            ) : slotsQuery.isError ? (
              <p className="m-0 text-sm text-ui-late">Bezorgtijden ophalen is mislukt.</p>
            ) : slots.every((s) => !s.is_available) ? (
              <p className="m-0 text-sm text-ui-muted">Picnic heeft op dit moment geen bezorgmomenten vrij.</p>
            ) : (
              <SlotPicker
                slots={slots}
                selectedId={cart.selected_slot_id}
                chosen={cart.slot_chosen}
                onPick={(slot) => slotMutation.mutate(slot)}
                busy={slotMutation.isPending}
              />
            )}
            {slotMutation.isError && <p className="m-0 text-sm text-ui-late">Dat bezorgmoment kiezen is mislukt; misschien is het net vol.</p>}
          </section>

          {error && <div className="rounded-2xl bg-ui-late-soft px-4 py-3.5 text-sm font-semibold text-ui-late">{error}</div>}

          <button
            type="button"
            onClick={() => {
              setError(null);
              setConfirming(true);
            }}
            disabled={!canOrder || !!pending}
            className={`${primaryButtonClass} w-full sm:w-auto sm:self-end`}
          >
            Bestellen · {formatEur(cart.checkout_total)}
          </button>
          {!pending && !canOrder && (
            <p className="m-0 text-sm text-ui-muted sm:self-end">
              {!cart.slot_chosen || !selectedSlot
                ? "Kies eerst een bezorgmoment."
                : belowMinimum
                  ? `Voor dit moment is het minimum ${formatEur(selectedSlot.minimum_order)}.`
                  : "Dit bezorgmoment is niet meer beschikbaar; kies een ander."}
            </p>
          )}
        </>
      )}

      {confirming && cart && selectedSlot && (
        <ModalOverlay onClose={() => setConfirming(false)} cardClassName="flex w-full max-w-sm flex-col gap-3 rounded-[20px] bg-ui-surface p-5 shadow-lg">
          <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Bestelling plaatsen?</h2>
          <p className="m-0 text-[15px] text-ui-ink-soft">
            {cart.item_count} producten voor <span className="font-semibold text-ui-ink">{formatEur(cart.checkout_total)}</span>, bezorgd{" "}
            <span className="font-semibold text-ui-ink">{slotLabel(selectedSlot)}</span>.
          </p>
          <p className="m-0 text-sm text-ui-muted">
            Je gaat naar je bank om te betalen (iDEAL). Pas als je de betaling daar goedkeurt, is de bestelling geplaatst.
          </p>
          <div className="mt-1 flex justify-end gap-2">
            <button type="button" onClick={() => setConfirming(false)} className={secondaryButtonClass}>
              Annuleren
            </button>
            <button type="button" onClick={() => checkoutMutation.mutate()} disabled={checkoutMutation.isPending} className={`${primaryButtonClass} h-11`}>
              {checkoutMutation.isPending ? "Bezig…" : "Naar betalen"}
            </button>
          </div>
        </ModalOverlay>
      )}
    </div>
  );
}
