import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { GriprAccount, GriprCategory } from "../../api/griprTypes";
import TransactionBulkBar from "./TransactionBulkBar";

function category(id: number, name: string, extra: Partial<GriprCategory> = {}): GriprCategory {
  return { id, name, kind: "expense", parent_id: null, is_archived: false, color: null, linked_loan_account_id: null, ...extra };
}

const accounts = [{ id: 7, name: "ING" }, { id: 8, name: "Gezamenlijk" }] as GriprAccount[];
const categories = [
  category(1, "Boodschappen"),
  category(11, "Markt", { parent_id: 1 }),
  category(12, "Oud", { parent_id: 1, is_archived: true }),
  category(2, "Salaris", { kind: "income" }),
];

function renderBar() {
  const handlers = { onSetCategory: vi.fn(), onSetAccount: vi.fn(), onDelete: vi.fn(), onClear: vi.fn() };
  render(<TransactionBulkBar count={3} categories={categories} accounts={accounts} busy={false} {...handlers} />);
  return handlers;
}

describe("TransactionBulkBar", () => {
  it("offers subcategories under their parent, without archived ones", () => {
    renderBar();

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("Boodschappen › Markt");
    expect(options).not.toContain("Boodschappen › Oud");
    expect(screen.getByText("3 selected")).toBeInTheDocument();
  });

  it("files the selection under the picked category, only once one is picked", async () => {
    const { onSetCategory } = renderBar();
    const file = screen.getByRole("button", { name: "File" });
    expect(file).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText("Category for the selection"), "11");
    await userEvent.click(file);

    expect(onSetCategory).toHaveBeenCalledWith(11);
  });

  it("moves to an account and deletes", async () => {
    const { onSetAccount, onDelete } = renderBar();

    await userEvent.selectOptions(screen.getByLabelText("Account for the selection"), "8");
    await userEvent.click(screen.getByRole("button", { name: "Move" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(onSetAccount).toHaveBeenCalledWith(8);
    expect(onDelete).toHaveBeenCalled();
  });
});
