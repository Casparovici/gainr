import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import { usePortfolio } from "../hooks/usePortfolio";

/** Which gainr portfolio (e.g. "Main", "Kids") Home/Transactions/Journal are scoped to --
 * visually the same collapsed-pill-that-expands-on-click shape as ModuleSwitcher, but it
 * changes a query parameter every gainr page reads rather than navigating. */
/** `variant="pill"` matches the page kit's module pill, for a gainr page's own top row on a phone
 * (where the header holding the default version is hidden). */
export default function PortfolioSwitcher({ variant = "default" }: { variant?: "default" | "pill" }) {
  const queryClient = useQueryClient();
  const { portfolios, portfolioId, setPortfolioId, isLoading } = usePortfolio();
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setAdding(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  const active = portfolios.find((p) => p.id === portfolioId);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    const created = await api.createPortfolio(name);
    queryClient.invalidateQueries({ queryKey: ["portfolios"] });
    setPortfolioId(created.id);
    setNewName("");
    setAdding(false);
    setOpen(false);
  }

  if (isLoading) return null;

  // A brand-new database with no portfolio yet (created straight from Base.metadata, never
  // run through the migration that seeds "Main") still needs a way to create the first one --
  // the pill shows "+ New portfolio" itself rather than disappearing with nothing to click.
  if (!active) {
    return (
      <div ref={containerRef} className="relative">
        <button
          type="button"
          onClick={() => {
            setOpen(true);
            setAdding(true);
          }}
          className="rounded-lg border border-dashed border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-500 transition-colors hover:border-slate-400 hover:text-slate-700"
        >
          + New portfolio
        </button>
        {open && (
          <div className="absolute left-0 top-full z-30 mt-1 min-w-full overflow-hidden rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
            <form onSubmit={handleAdd} className="flex gap-1 px-1 py-1">
              <input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Portfolio name"
                className="w-32 rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              />
              <button
                type="submit"
                className="rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white hover:bg-slate-800"
              >
                Add
              </button>
            </form>
          </div>
        )}
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={
          variant === "pill"
            ? "flex h-11 items-center gap-1.5 rounded-full border border-ui-border bg-ui-surface pl-4 pr-3 text-[15px] font-semibold text-ui-ink"
            : "flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        }
        aria-haspopup="true"
        aria-expanded={open}
      >
        {active.name}
        <ChevronDown className="h-3.5 w-3.5 opacity-70" strokeWidth={2} />
      </button>

      {open && (
        <div
          className={`absolute top-full z-30 mt-1 min-w-full overflow-hidden rounded-lg border border-slate-200 bg-white p-1 shadow-lg ${
            variant === "pill" ? "right-0" : "left-0"
          }`}
        >
          {portfolios.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => {
                setPortfolioId(p.id);
                setOpen(false);
              }}
              className={`block w-full whitespace-nowrap rounded-md px-3 py-1.5 text-left text-sm font-medium transition-colors ${
                p.id === active.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {p.name}
            </button>
          ))}

          <div className="mt-1 border-t border-slate-100 pt-1">
            {adding ? (
              <form onSubmit={handleAdd} className="flex gap-1 px-1 py-1">
                <input
                  autoFocus
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Portfolio name"
                  className="w-32 rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
                <button
                  type="submit"
                  className="rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white hover:bg-slate-800"
                >
                  Add
                </button>
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setAdding(true)}
                className="block w-full whitespace-nowrap rounded-md px-3 py-1.5 text-left text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              >
                + New portfolio
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
