import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Transaction } from "../api/types";
import TransactionSheet from "./TransactionSheet";

const buy: Transaction = {
  id: 7, date: "2026-09-11", type: "Buy", portfolio_id: 1, asset_id: 3, quantity: "5", price: "82", local_value: "410",
  fx_rate: "1", value_eur: "410", costs: "0", total_eur: "410", broker: "Trading 212", to_broker: null, notes: null,
  ticker: "IWDA", asset_name: "iShares Core MSCI World", native_currency: "EUR", attachment_count: 0,
};

function renderSheet(extra: Partial<Parameters<typeof TransactionSheet>[0]> = {}) {
  const handlers = { onClose: vi.fn(), onEdit: vi.fn(), onDuplicate: vi.fn(), onDelete: vi.fn(), onOpenPosition: vi.fn() };
  render(<TransactionSheet transaction={buy} {...handlers} {...extra} />);
  return handlers;
}

afterEach(() => vi.restoreAllMocks());

describe("TransactionSheet", () => {
  it("shows the transaction and offers edit, duplicate and the position", async () => {
    const h = renderSheet();
    expect(screen.getByRole("dialog", { name: /Buy/ })).toBeInTheDocument();
    expect(screen.getByText("iShares Core MSCI World")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
    await userEvent.click(screen.getByRole("button", { name: /Open position: IWDA/ }));
    expect([h.onEdit, h.onDuplicate, h.onOpenPosition].every((f) => f.mock.calls.length === 1)).toBe(true);
  });

  it("deletes only after a confirmation", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const h = renderSheet();
    await userEvent.click(screen.getByRole("button", { name: /Delete transaction/ }));
    expect(h.onDelete).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Delete transaction/ }));
    expect(h.onDelete).toHaveBeenCalledTimes(1);
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it("closes on Escape", async () => {
    const h = renderSheet();
    await userEvent.keyboard("{Escape}");
    expect(h.onClose).toHaveBeenCalled();
  });
});
