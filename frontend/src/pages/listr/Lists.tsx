import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, ReceiptEuro, ShoppingCart, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import NewListForm from "../../components/listr/NewListForm";
import { IconChevronRight, IconPlus, ModuleTopRow, PageTitle, dashedButtonClass, secondaryButtonClass } from "../../components/ui/kit";

function formatUpdatedAt(iso: string): string {
  return new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });
}

export default function ListrLists() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  const { data: lists, isLoading } = useQuery({
    queryKey: ["listr-lists", showArchived],
    queryFn: () => listrApi.listLists(showArchived),
  });

  // Same key usePicnicConnect uses, so the two share one cached status.
  const picnicStatusQuery = useQuery({ queryKey: ["listr-picnic-status"], queryFn: () => listrApi.picnicStatus() });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["listr-lists"] });

  const createMutation = useMutation({
    mutationFn: (name: string) => listrApi.createList(name),
    onSuccess: (list) => {
      invalidate();
      setCreating(false);
      navigate(`/listr/lijst/${list.id}`);
    },
  });
  const archiveMutation = useMutation({
    mutationFn: ({ id, is_archived }: { id: number; is_archived: boolean }) =>
      listrApi.updateList(id, { is_archived }),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => listrApi.deleteList(id),
    onSuccess: invalidate,
  });
  const duplicateMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => listrApi.duplicateList(id, name),
    onSuccess: (list) => {
      invalidate();
      navigate(`/listr/lijst/${list.id}`);
    },
  });

  const open = (lists ?? []).filter((l) => !l.is_archived).reduce((sum, l) => sum + l.item_count - l.checked_count, 0);

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        {picnicStatusQuery.data?.configured && (
          <>
            <Link to="/listr/winkelwagen" aria-label="Picnic-winkelwagen" className={`${secondaryButtonClass} no-underline`}>
              <ShoppingCart className="h-[18px] w-[18px]" strokeWidth={2} />
              <span className="hidden sm:inline">Winkelwagen</span>
            </Link>
            <Link to="/listr/bestellingen" aria-label="Picnic-bestellingen" className={`${secondaryButtonClass} no-underline`}>
              <ReceiptEuro className="h-[18px] w-[18px]" strokeWidth={2} />
              <span className="hidden sm:inline">Bestellingen</span>
            </Link>
          </>
        )}
        <label className={`${secondaryButtonClass} cursor-pointer text-sm font-medium`} title="Toon gearchiveerde lijsten">
          <input type="checkbox" className="h-4 w-4 accent-ui-brand" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          <Archive className="h-4 w-4 sm:hidden" strokeWidth={2} aria-label="Gearchiveerd" />
          <span className="hidden sm:inline">Gearchiveerd</span>
        </label>
      </ModuleTopRow>
      <PageTitle subtitle={lists && lists.length > 0 ? `${lists.length} ${lists.length === 1 ? "lijst" : "lijsten"} · ${open} nog te halen` : undefined}>
        Lijsten
      </PageTitle>

      {isLoading ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>
      ) : !lists || lists.length === 0 ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted">
          Nog geen lijsten — maak er hieronder een aan om te beginnen.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {lists.map((list) => (
            <div
              key={list.id}
              onClick={() => navigate(`/listr/lijst/${list.id}`)}
              className={`flex cursor-pointer flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface p-4 transition-colors hover:border-ui-line ${
                list.is_archived ? "opacity-60" : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-ui-brand-soft text-ui-brand-strong">
                  <ShoppingCart className="h-5 w-5" strokeWidth={2} />
                </span>
                <div className="flex min-w-0 flex-grow flex-col gap-0.5">
                  <span className="truncate font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{list.name}</span>
                  <span className="text-sm text-ui-muted">
                    {list.item_count === 0 ? "Nog leeg" : `${list.checked_count} / ${list.item_count} afgevinkt`}
                    {" · "}
                    {formatUpdatedAt(list.updated_at)}
                  </span>
                </div>
                {list.is_archived ? (
                  <span className="shrink-0 rounded-full bg-ui-tile px-2.5 py-1 text-xs font-semibold text-ui-muted">gearchiveerd</span>
                ) : (
                  <span className="shrink-0 text-ui-muted">
                    <IconChevronRight size={20} />
                  </span>
                )}
              </div>
              {list.item_count > 0 && (
                <div className="h-1.5 overflow-hidden rounded-full bg-ui-tile" aria-hidden>
                  <div className="h-full rounded-full bg-ui-brand" style={{ width: `${(list.checked_count / list.item_count) * 100}%` }} />
                </div>
              )}
              <div
                className="flex items-center justify-between border-t border-ui-border pt-2 text-sm text-ui-muted"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex gap-4">
                  <button
                    type="button"
                    onClick={() => duplicateMutation.mutate({ id: list.id, name: `${list.name} (kopie)` })}
                    className="py-1 font-medium hover:text-ui-ink"
                  >
                    Dupliceren
                  </button>
                  <button
                    type="button"
                    onClick={() => archiveMutation.mutate({ id: list.id, is_archived: !list.is_archived })}
                    className="py-1 hover:text-ui-ink"
                    title={list.is_archived ? "Herstellen" : "Archiveren"}
                    aria-label={list.is_archived ? "Herstellen" : "Archiveren"}
                  >
                    {list.is_archived ? <ArchiveRestore className="h-4 w-4" strokeWidth={2} /> : <Archive className="h-4 w-4" strokeWidth={2} />}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`Lijst "${list.name}" verwijderen? Dit kan niet ongedaan worden gemaakt.`)) {
                      deleteMutation.mutate(list.id);
                    }
                  }}
                  className="py-1 text-ui-late"
                  title="Verwijderen"
                  aria-label="Verwijderen"
                >
                  <Trash2 className="h-4 w-4" strokeWidth={2} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <button type="button" onClick={() => setCreating(true)} className={dashedButtonClass}>
        <IconPlus size={20} />
        Nieuwe lijst
      </button>

      {creating && (
        <NewListForm
          isSubmitting={createMutation.isPending}
          onCancel={() => setCreating(false)}
          onSubmit={(name) => createMutation.mutate(name)}
        />
      )}
    </div>
  );
}
