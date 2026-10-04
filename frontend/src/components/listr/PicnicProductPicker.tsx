import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingCart, X } from "lucide-react";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrPicnicProduct } from "../../api/listrTypes";
import { formatEur } from "../../utils/format";
import ModalOverlay from "../ModalOverlay";
import { inputClass } from "../ui/kit";
import PicnicThumb from "./PicnicThumb";

/** Search Picnic's own catalog and pick which product a listr catalog item means -- a
 * one-time action per item (see docs/adr/0011-listr-picnic-integration.md), remembered from
 * then on. Only rendered once connected to Picnic (see ListDetail.tsx). Opening the picker
 * searches Picnic using the ingredient's own name right away -- the app already knows it, so
 * the reader shouldn't have to type it again before picking the matching result.
 *
 * A centred dialog rather than a dropdown under the cart icon: the list's category cards clip
 * their contents (rounded corners), and on a phone a dropdown under the last rows would sit
 * behind the bottom bar -- either way most results ended up out of sight. */
export default function PicnicProductPicker({
  groceryItemId,
  itemName,
  mappedName,
}: {
  groceryItemId: number;
  itemName: string;
  mappedName: string | null;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const trimmed = query.trim();
  const searchQuery = useQuery({
    queryKey: ["listr-picnic-search", trimmed],
    queryFn: () => listrApi.picnicSearch(trimmed),
    enabled: open && trimmed.length > 1,
  });

  const close = () => {
    setOpen(false);
    setQuery("");
  };

  const mapMutation = useMutation({
    mutationFn: (product: ListrPicnicProduct) =>
      listrApi.setItemPicnicMapping(groceryItemId, {
        picnic_product_id: product.id,
        picnic_product_name: product.name,
        display_price: product.display_price ?? null,
        unit_quantity: product.unit_quantity || null,
        image_id: product.image_id ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listr-items"] });
      queryClient.invalidateQueries({ queryKey: ["listr-list"] });
      close();
    },
  });

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setQuery(itemName);
          setOpen(true);
        }}
        title={mappedName ? `Picnic: ${mappedName} (klik om te wijzigen)` : "Koppel aan Picnic-product"}
        aria-label={mappedName ? `Picnic: ${mappedName}` : "Koppel aan Picnic-product"}
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
          mappedName ? "text-emerald-600 hover:text-emerald-700" : "text-ui-faint hover:text-ui-muted"
        }`}
      >
        <ShoppingCart className="h-4 w-4" strokeWidth={2} />
      </button>

      {open && (
        <ModalOverlay
          onClose={close}
          cardClassName="flex max-h-[85vh] w-full max-w-md flex-col gap-3 rounded-[20px] bg-ui-surface p-4 shadow-lg"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-col gap-0.5">
              <h2 className="m-0 truncate font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Picnic-product</h2>
              <p className="m-0 truncate text-sm text-ui-muted">
                Voor {itemName}
                {mappedName && ` · nu: ${mappedName}`}
              </p>
            </div>
            <button
              type="button"
              onClick={close}
              aria-label="Sluiten"
              className="-mr-1 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ui-muted hover:text-ui-ink"
            >
              <X className="h-5 w-5" strokeWidth={2} />
            </button>
          </div>

          <input
            autoFocus
            inputMode="search"
            enterKeyHint="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Zoek op Picnic…"
            aria-label="Zoek op Picnic"
            className={inputClass}
          />

          <div className="-mx-1 min-h-0 flex-1 overflow-y-auto">
            {trimmed.length <= 1 ? (
              <p className="m-0 px-1 py-2 text-sm text-ui-muted">Typ om te zoeken…</p>
            ) : searchQuery.isLoading ? (
              <p className="m-0 px-1 py-2 text-sm text-ui-muted">Zoeken…</p>
            ) : searchQuery.isError ? (
              <p className="m-0 px-1 py-2 text-sm text-ui-late">Zoeken mislukt. Probeer het opnieuw.</p>
            ) : searchQuery.data?.length === 0 ? (
              <p className="m-0 px-1 py-2 text-sm text-ui-muted">Niets gevonden. Probeer een ander woord.</p>
            ) : (
              <ul className="m-0 list-none divide-y divide-ui-border p-0">
                {searchQuery.data?.map((product) => {
                  const current = product.name === mappedName;
                  return (
                    <li key={product.id}>
                      <button
                        type="button"
                        onClick={() => mapMutation.mutate(product)}
                        disabled={mapMutation.isPending}
                        aria-current={current ? "true" : undefined}
                        className={`flex min-h-[52px] w-full items-center justify-between gap-3 rounded-lg px-2 py-2 text-left hover:bg-ui-tile disabled:opacity-60 ${
                          current ? "bg-ui-brand-soft" : ""
                        }`}
                      >
                        <span className="flex min-w-0 items-center gap-3">
                          <PicnicThumb url={product.image_url} size={40} />
                          <span className="min-w-0 text-[15px] text-ui-ink">{product.name}</span>
                        </span>
                        <span className="flex shrink-0 flex-col items-end text-xs text-ui-muted">
                          {product.display_price != null && (
                            <span className="text-sm font-semibold text-ui-ink">{formatEur(product.display_price / 100)}</span>
                          )}
                          {product.unit_quantity}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          {mapMutation.isError && <p className="m-0 text-sm text-ui-late">Koppelen is mislukt. Probeer het opnieuw.</p>}
        </ModalOverlay>
      )}
    </>
  );
}
