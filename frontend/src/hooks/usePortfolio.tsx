import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "../api/client";
import type { Portfolio } from "../api/types";

const STORAGE_KEY = "pdt-gainr-portfolio-id";

function readStoredPortfolioId(): number | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? Number(stored) : null;
  } catch {
    return null;
  }
}

interface PortfolioContextValue {
  portfolios: Portfolio[];
  portfolioId: number | null;
  setPortfolioId: (id: number) => void;
  isLoading: boolean;
  /** The portfolio list couldn't be loaded -- not the same as having none yet. */
  isError: boolean;
  refetch: () => void;
}

const PortfolioContext = createContext<PortfolioContextValue | null>(null);

/** Which gainr portfolio is currently selected -- mirrors useTheme's context + localStorage +
 * small-header-control shape. Defaults to the stored choice if it still exists, else the first
 * (non-archived) portfolio, so a fresh browser lands on "Main" without the user picking it. */
export function PortfolioProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [portfolioId, setPortfolioIdState] = useState<number | null>(readStoredPortfolioId);

  const query = useQuery({ queryKey: ["portfolios"], queryFn: () => api.listPortfolios() });
  const portfolios = query.data ?? [];

  useEffect(() => {
    if (portfolios.length === 0) return;
    if (portfolioId !== null && portfolios.some((p) => p.id === portfolioId)) return;
    setPortfolioIdState(portfolios[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolios]);

  const setPortfolioId = (id: number) => {
    setPortfolioIdState(id);
    try {
      localStorage.setItem(STORAGE_KEY, String(id));
    } catch {
      // Nothing to persist to — the choice just won't survive a reload.
    }
    // Every gainr query keys off portfolioId, so switching invalidates the lot at once rather
    // than each page independently discovering the id changed.
    queryClient.invalidateQueries({ queryKey: ["summary"] });
    queryClient.invalidateQueries({ queryKey: ["positions"] });
    queryClient.invalidateQueries({ queryKey: ["performance"] });
    queryClient.invalidateQueries({ queryKey: ["transactions"] });
    queryClient.invalidateQueries({ queryKey: ["brokers"] });
  };

  return (
    <PortfolioContext.Provider value={{
        portfolios,
        portfolioId,
        setPortfolioId,
        isLoading: query.isLoading,
        isError: query.isError,
        refetch: () => void query.refetch(),
      }}>
      {children}
    </PortfolioContext.Provider>
  );
}

export function usePortfolio(): PortfolioContextValue {
  const ctx = useContext(PortfolioContext);
  if (!ctx) throw new Error("usePortfolio must be used within a PortfolioProvider");
  return ctx;
}

/** The selected portfolio's id where a PortfolioProvider is above (always, in the app), else
 * null -- for app-wide chrome like the module switcher that shouldn't need one to render. */
export function useSelectedPortfolioId(): number | null {
  return useContext(PortfolioContext)?.portfolioId ?? null;
}
