import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AppNotification } from "../api/types";
import NotificationBell from "./NotificationBell";

const load = vi.fn();

const hourAgo = new Date(Date.now() - 3_600_000).toISOString();
const lastLook = new Date(Date.now() - 2 * 3_600_000).toISOString();
const SYNCED: AppNotification = {
  key: "synced:ING", kind: "synced", at: hourAgo, title: "5 new transactions from ING", detail: "2 need a category",
  link: "/gripr/transactions?category=uncategorized",
};
const OLD_BANK: AppNotification = {
  key: "bank:tr:error", kind: "bank", at: "2026-10-03T05:15:00Z", title: "Trade Republic isn't syncing", detail: "Daily limit", link: "/gripr",
};

function renderBell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NotificationBell storageKey="gripr.notifications.seenAt" queryKey="gripr-notifications" load={load} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("shows a dot for what's new since this device last looked, and clears it on close", async () => {
    localStorage.setItem("gripr.notifications.seenAt", lastLook);
    vi.mocked(load).mockResolvedValue([SYNCED, OLD_BANK]);
    renderBell();

    const bell = await screen.findByRole("button", { name: "Notifications — 1 new" });
    expect(load).toHaveBeenCalledWith(lastLook);

    await userEvent.click(bell);
    const dialog = screen.getByRole("heading", { name: "Since your last visit" }).closest("div")!.parentElement!;
    expect(within(dialog).getByText("5 new transactions from ING")).toHaveClass("font-semibold");
    expect(within(dialog).getByText("Trade Republic isn't syncing")).not.toHaveClass("font-semibold");
    expect(within(dialog).getByRole("link", { name: /5 new transactions/ })).toHaveAttribute("href", "/gripr/transactions?category=uncategorized");

    vi.mocked(load).mockResolvedValue([OLD_BANK]);
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(Date.parse(localStorage.getItem("gripr.notifications.seenAt")!)).toBeGreaterThan(Date.parse(hourAgo));
  });

  it("says when there's nothing new", async () => {
    vi.mocked(load).mockResolvedValue([]);
    renderBell();

    await userEvent.click(await screen.findByRole("button", { name: "Notifications" }));

    expect(screen.getByText(/Nothing new/)).toBeInTheDocument();
  });
});

describe("NotificationBell per module", () => {
  it("remembers the last look separately for each module", async () => {
    localStorage.clear();
    load.mockResolvedValue([]);
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <NotificationBell storageKey="gainr.notifications.seenAt" queryKey="gainr-notifications" load={load} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Notifications" }));
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(localStorage.getItem("gainr.notifications.seenAt")).not.toBeNull();
    expect(localStorage.getItem("gripr.notifications.seenAt")).toBeNull();
  });
});
