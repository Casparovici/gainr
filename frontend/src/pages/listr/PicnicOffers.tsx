import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShoppingCart } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import type { ListrPicnicCart, ListrPicnicPromoProduct } from "../../api/listrTypes";
import PicnicConnectCard from "../../components/listr/PicnicConnectCard";
import { IconChevronLeft, ModuleTopRow, PageTitle, inputClass, secondaryButtonClass } from "../../components/ui/kit";
import { usePicnicConnect } from "../../hooks/usePicnicConnect";
import { formatEur } from "../../utils/format";
import { t } from "../../i18n";

const sectionAnchor = (index: number) => `aanbieding-sectie-${index}`;

function OfferCard({
  offer,
  inCart,
  onAdd,
  adding,
}: {
  offer: ListrPicnicPromoProduct;
  inCart: number;
  onAdd: () => void;
  adding: boolean;
}) {
  return (
    <li className="flex flex-col gap-2 rounded-2xl border border-ui-border bg-ui-surface p-2.5">
      <div className="relative flex aspect-square items-center justify-center overflow-hidden rounded-xl bg-[#fff]">
        {offer.image_url && <img src={offer.image_url.replace("/small.png", "/medium.png")} alt="" loading="lazy" className="h-full w-full object-contain p-2" />}
        <span className="absolute left-1.5 top-1.5 max-w-[calc(100%-12px)] truncate rounded-full bg-ui-brand-soft px-2 py-0.5 text-[12px] font-bold text-ui-brand-strong">
          {offer.label}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-0.5 px-0.5">
        <span className="line-clamp-2 text-sm font-medium leading-snug text-ui-ink">{offer.name}</span>
        <span className="text-xs text-ui-muted">{offer.unit_quantity}</span>
      </div>
      <div className="flex items-end justify-between gap-2 px-0.5">
        <span className="flex flex-col leading-tight">
          {offer.original_price && <span className="text-xs text-ui-muted line-through">{formatEur(offer.original_price)}</span>}
          <span className="text-[15px] font-bold tabular-nums text-ui-ink">{formatEur(offer.price)}</span>
        </span>
        <button
          type="button"
          onClick={onAdd}
          disabled={adding}
          aria-label={inCart ? t("Nog een {name} in winkelwagen ({count} erin)", { name: offer.name, count: inCart }) : t("{name} in winkelwagen", { name: offer.name })}
          className={`flex h-10 shrink-0 items-center justify-center gap-1 rounded-xl px-2.5 text-sm font-semibold disabled:opacity-50 ${
            inCart ? "bg-ui-brand-soft text-ui-brand-strong" : "bg-ui-brand text-white hover:bg-ui-brand-strong"
          }`}
        >
          {inCart > 0 && <span className="tabular-nums">{inCart}</span>}
          <Plus className="h-4 w-4" strokeWidth={2.5} />
        </button>
      </div>
    </li>
  );
}

/** This week's Picnic offers, in Picnic's own sections, each addable to the Picnic cart with
 * one tap -- the products that are cheaper now, for when something catches the eye. Read from
 * Picnic's Aanbiedingen tab (see listr_picnic_service.promotions). */
export default function ListrPicnicOffers() {
  const queryClient = useQueryClient();
  const picnic = usePicnicConnect(() => queryClient.invalidateQueries({ queryKey: ["listr-picnic-promotions"] }));
  const connected = picnic.status?.connected ?? false;
  const [filter, setFilter] = useState("");

  const promotionsQuery = useQuery({
    queryKey: ["listr-picnic-promotions"],
    queryFn: () => listrApi.picnicPromotions(),
    enabled: connected,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
  const cartQuery = useQuery({ queryKey: ["listr-picnic-cart"], queryFn: () => listrApi.picnicCart(), enabled: connected, retry: false });
  const expired = [promotionsQuery.error, cartQuery.error].some((e) => e instanceof Error && e.message.startsWith("409"));
  useEffect(() => {
    if (expired) queryClient.invalidateQueries({ queryKey: ["listr-picnic-status"] });
  }, [expired, queryClient]);

  const [lastAdded, setLastAdded] = useState<string | null>(null);
  const addMutation = useMutation({
    mutationFn: (offer: ListrPicnicPromoProduct) => listrApi.picnicCartAdd(offer.id),
    onSuccess: (cart: ListrPicnicCart, offer) => {
      queryClient.setQueryData(["listr-picnic-cart"], cart);
      setLastAdded(offer.name);
    },
  });

  const inCart = useMemo(() => new Map((cartQuery.data?.lines ?? []).map((l) => [l.product_id, l.count])), [cartQuery.data]);
  const needle = filter.trim().toLowerCase();
  const sections = (promotionsQuery.data ?? [])
    .map((section) => ({ ...section, products: needle ? section.products.filter((p) => p.name.toLowerCase().includes(needle)) : section.products }))
    .filter((section) => section.products.length > 0);
  const total = (promotionsQuery.data ?? []).reduce((n, s) => n + s.products.length, 0);
  const cartCount = cartQuery.data?.item_count ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow
        left={
          <Link to="/listr/winkelwagen" aria-label={t("Terug naar winkelwagen")} className={`${secondaryButtonClass} pl-2 pr-3 no-underline`}>
            <IconChevronLeft size={20} />{t("Winkelwagen")}</Link>
        }
      >
        <Link to="/listr/winkelwagen" aria-label={t("Winkelwagen, {count} producten", { count: cartCount })} className={`${secondaryButtonClass} relative no-underline`}>
          <ShoppingCart className="h-[18px] w-[18px]" strokeWidth={2} />
          {cartCount > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-ui-brand px-1 text-[11px] font-bold text-white">
              {cartCount}
            </span>
          )}
        </Link>
      </ModuleTopRow>
      <PageTitle subtitle={promotionsQuery.data ? t("{total} aanbiedingen bij Picnic", { total }) : t("Deze week bij Picnic")}>{t("Aanbiedingen")}</PageTitle>

      {!picnic.status ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">{t("Laden…")}</div>
      ) : !picnic.status.configured || !connected ? (
        <PicnicConnectCard picnic={picnic} reason={t("Verbind met Picnic om de aanbiedingen te zien.")} />
      ) : promotionsQuery.isLoading ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">{t("Aanbiedingen ophalen bij Picnic…")}</div>
      ) : promotionsQuery.isError ? (
        <div className="rounded-2xl bg-ui-late-soft px-4 py-3.5 text-[15px] font-semibold text-ui-late">{t("Aanbiedingen ophalen is mislukt. Probeer het later opnieuw.")}</div>
      ) : total === 0 ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">{t("Picnic heeft nu geen aanbiedingen.")}</div>
      ) : (
        <>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            inputMode="search"
            placeholder={t("Zoek in de aanbiedingen…")}
            aria-label={t("Zoek in de aanbiedingen")}
            className={`${inputClass} sm:max-w-sm`}
          />
          <nav aria-label={t("Secties")} className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none]">
            {sections.map((section, i) => (
              <a
                key={section.title + i}
                href={`#${sectionAnchor(i)}`}
                className="flex h-9 shrink-0 items-center rounded-full border border-ui-border bg-ui-surface px-3.5 text-sm font-semibold text-ui-ink-soft no-underline hover:border-ui-line"
              >
                {section.title}
              </a>
            ))}
          </nav>
          {lastAdded && (
            <p className="m-0 text-sm text-ui-ink-soft" role="status">
              {lastAdded}{" "}{t("staat in je winkelwagen.")}{" "}
              <Link to="/listr/winkelwagen" className="font-semibold text-ui-brand-strong">{t("Naar winkelwagen ›")}</Link>
            </p>
          )}
          {addMutation.isError && <p className="m-0 text-sm text-ui-late">{t("Toevoegen is mislukt. Probeer het opnieuw.")}</p>}
          {sections.length === 0 && <p className="m-0 text-sm text-ui-muted">{t("Geen aanbieding met \"{filter}\".", { filter: filter })}</p>}
          {sections.map((section, i) => (
            <section key={section.title + i} id={sectionAnchor(i)} className="flex scroll-mt-4 flex-col gap-2">
              <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{section.title}</h2>
              <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3 lg:grid-cols-5">
                {section.products.map((offer) => (
                  <OfferCard
                    key={offer.id}
                    offer={offer}
                    inCart={inCart.get(offer.id) ?? 0}
                    onAdd={() => addMutation.mutate(offer)}
                    adding={addMutation.isPending && addMutation.variables?.id === offer.id}
                  />
                ))}
              </ul>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
