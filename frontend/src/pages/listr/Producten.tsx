import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, RefreshCw } from "lucide-react";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrItem } from "../../api/listrTypes";
import { IconPlus, ModuleTopRow, PageTitle, primaryButtonClass, secondaryButtonClass } from "../../components/ui/kit";
import PicnicThumb from "../../components/listr/PicnicThumb";
import { categoryIcon } from "../../utils/categoryIcons";
import { formatEur } from "../../utils/format";

const inputClass =
  "h-10 rounded-[10px] border border-ui-line bg-ui-surface px-3 text-[15px] text-ui-ink focus:border-ui-brand focus:outline-none focus:ring-1 focus:ring-ui-brand";

function NewItemRow({ categoryId, onAdded }: { categoryId: number; onAdded: () => void }) {
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("stuks");
  const [open, setOpen] = useState(false);

  const createMutation = useMutation({
    mutationFn: () => listrApi.createItem({ name: name.trim(), category_id: categoryId, default_unit: unit }),
    onSuccess: () => {
      setName("");
      setUnit("stuks");
      setOpen(false);
      onAdded();
    },
  });

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-11 w-full items-center gap-1.5 px-4 text-left text-sm font-semibold text-ui-brand-strong hover:bg-ui-tile"
      >
        <IconPlus size={16} />
        Nieuw product
      </button>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim() && unit.trim()) createMutation.mutate();
      }}
      className="flex items-center gap-1.5 px-3 py-2"
    >
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Naam"
        className={`${inputClass} min-w-0 flex-1`}
      />
      <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="eenheid" className={`${inputClass} w-20 min-w-0`} />
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="flex h-10 w-8 shrink-0 items-center justify-center text-sm text-ui-muted hover:text-ui-ink"
        title="Annuleren"
      >
        ✕
      </button>
      <button
        type="submit"
        disabled={createMutation.isPending}
        className={`${primaryButtonClass} h-10 shrink-0 px-3`}
      >
        Toevoegen
      </button>
    </form>
  );
}

export default function ListrProducten() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");

  const { data: categories } = useQuery({
    queryKey: ["listr-categories"],
    queryFn: () => listrApi.listCategories(),
  });
  const { data: items, isLoading } = useQuery({
    queryKey: ["listr-items", showArchived],
    queryFn: () => listrApi.listItems({ includeArchived: showArchived }),
  });

  const invalidateItems = () => queryClient.invalidateQueries({ queryKey: ["listr-items"] });

  const picnicStatusQuery = useQuery({ queryKey: ["listr-picnic-status"], queryFn: () => listrApi.picnicStatus() });
  const [priceFeedback, setPriceFeedback] = useState<string | null>(null);
  const refreshPricesMutation = useMutation({
    mutationFn: () => listrApi.refreshPicnicPrices(),
    onSuccess: (result) => {
      invalidateItems();
      setPriceFeedback(
        `${result.updated} ${result.updated === 1 ? "prijs" : "prijzen"} bijgewerkt` +
          (result.not_found.length ? ` · niet meer bij Picnic: ${result.not_found.join(", ")}` : "."),
      );
    },
    onError: () => setPriceFeedback("Prijzen bijwerken is mislukt. Is Picnic verbonden? Verbind via een lijst of Bestellingen."),
  });

  const archiveMutation = useMutation({
    mutationFn: ({ id, is_archived }: { id: number; is_archived: boolean }) =>
      listrApi.updateItem(id, { is_archived }),
    onSuccess: invalidateItems,
  });
  const createCategoryMutation = useMutation({
    mutationFn: (name: string) => listrApi.createCategory(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listr-categories"] });
      setNewCategoryName("");
    },
  });

  const itemsByCategory = new Map<number, ListrItem[]>();
  for (const item of items ?? []) {
    if (!itemsByCategory.has(item.category_id)) itemsByCategory.set(item.category_id, []);
    itemsByCategory.get(item.category_id)!.push(item);
  }

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        {picnicStatusQuery.data?.connected && (
          <button
            type="button"
            onClick={() => {
              setPriceFeedback(null);
              refreshPricesMutation.mutate();
            }}
            disabled={refreshPricesMutation.isPending}
            className={secondaryButtonClass}
            aria-label="Picnic-prijzen bijwerken"
            title="Picnic-prijzen bijwerken"
          >
            <RefreshCw className={`h-[18px] w-[18px] ${refreshPricesMutation.isPending ? "animate-spin" : ""}`} strokeWidth={2} />
            <span className="hidden sm:inline">{refreshPricesMutation.isPending ? "Bijwerken…" : "Prijzen bijwerken"}</span>
          </button>
        )}
        <label className={`${secondaryButtonClass} cursor-pointer text-sm font-medium`}>
          <input type="checkbox" className="h-4 w-4 accent-ui-brand" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          Gearchiveerd
        </label>
      </ModuleTopRow>
      <PageTitle
        subtitle={
          items && categories
            ? `${items.filter((i) => !i.is_archived).length} producten in ${categories.length} ${categories.length === 1 ? "categorie" : "categorieën"}`
            : undefined
        }
      >
        Producten
      </PageTitle>
      {priceFeedback && <p className="m-0 text-sm text-ui-ink-soft">{priceFeedback}</p>}

      {isLoading ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {(categories ?? []).map((category) => {
            const Icon = categoryIcon(category.name);
            const categoryItems = itemsByCategory.get(category.id) ?? [];
            return (
              <div key={category.id} className="overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
                <div className="flex items-center gap-2 border-b border-ui-border px-4 py-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ui-brand-soft text-ui-brand-strong">
                    <Icon className="h-4 w-4" strokeWidth={2} />
                  </span>
                  <span className="text-[15px] font-semibold text-ui-ink">{category.name}</span>
                  <span className="ml-auto text-sm text-ui-muted">{categoryItems.length}</span>
                </div>
                <ul className="divide-y divide-ui-border">
                  {categoryItems.map((item) => (
                    <li
                      key={item.id}
                      className={`flex min-h-[44px] items-center justify-between gap-2 pl-4 pr-2 text-[15px] ${
                        item.is_archived ? "text-ui-faint" : "text-ui-ink"
                      }`}
                    >
                      <span className="flex min-w-0 items-center gap-2.5">
                      {item.picnic_image_url && <PicnicThumb url={item.picnic_image_url} size={36} />}
                      <span className="flex min-w-0 flex-col py-1">
                        <span className="truncate">{item.name}</span>
                        {item.picnic_product_id && (
                          <span
                            className="truncate text-xs text-ui-muted"
                            title={item.picnic_price_at ? `Prijs van ${new Date(item.picnic_price_at).toLocaleDateString("nl-NL")}` : undefined}
                          >
                            Picnic: {item.picnic_product_name}
                            {item.picnic_price !== null && (
                              <>
                                {" · "}
                                <span className="font-semibold text-ui-ink-soft">{formatEur(item.picnic_price)}</span>
                                {item.picnic_unit_quantity && ` / ${item.picnic_unit_quantity}`}
                              </>
                            )}
                          </span>
                        )}
                      </span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2">
                        <span className="text-xs text-ui-muted">{item.default_unit}</span>
                        <button
                          type="button"
                          onClick={() => archiveMutation.mutate({ id: item.id, is_archived: !item.is_archived })}
                          className="flex h-9 w-9 items-center justify-center rounded-lg text-ui-faint hover:text-ui-ink"
                          title={item.is_archived ? "Herstellen" : "Archiveren"}
                          aria-label={item.is_archived ? "Herstellen" : "Archiveren"}
                        >
                          {item.is_archived ? <ArchiveRestore className="h-4 w-4" strokeWidth={2} /> : <Archive className="h-4 w-4" strokeWidth={2} />}
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="border-t border-ui-border">
                  <NewItemRow categoryId={category.id} onAdded={invalidateItems} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (newCategoryName.trim()) createCategoryMutation.mutate(newCategoryName.trim());
        }}
        className="flex items-center gap-2 rounded-[20px] border-2 border-dashed border-ui-line p-3"
      >
        <input
          value={newCategoryName}
          onChange={(e) => setNewCategoryName(e.target.value)}
          placeholder="Nieuwe categorie…"
          className={`${inputClass} flex-1`}
        />
        <button
          type="submit"
          disabled={createCategoryMutation.isPending}
          className={`${primaryButtonClass} h-10 px-3.5`}
        >
          <IconPlus size={18} />
          Categorie
        </button>
      </form>
    </div>
  );
}
