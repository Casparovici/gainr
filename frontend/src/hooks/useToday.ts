import { useQuery } from "@tanstack/react-query";

import { taskrApi } from "../api/taskrClient";
import { useSelectedPortfolioId } from "./usePortfolio";

// The counts change as things are done in other modules, whose mutations don't know this key; a
// few minutes' staleness is fine for badges, and the page refetches when it's opened again.
const TODAY_STALE_MS = 2 * 60_000;

/** Vandaag's data: the start screen's content and the module switcher's counts, one request
 * shared by both. */
export function useToday(enabled = true) {
  const portfolioId = useSelectedPortfolioId();
  return useQuery({
    queryKey: ["today", portfolioId],
    queryFn: () => taskrApi.getToday(portfolioId),
    staleTime: TODAY_STALE_MS,
    enabled,
  });
}
