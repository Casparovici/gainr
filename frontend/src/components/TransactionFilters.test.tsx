import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TransactionFilters, { EMPTY_FILTERS } from "./TransactionFilters";

describe("TransactionFilters", () => {
  it("filters on a type chip and toggles it off again", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<TransactionFilters filters={EMPTY_FILTERS} onChange={onChange} brokers={[]} />);
    await userEvent.click(screen.getByRole("button", { name: "Dividends" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY_FILTERS, type: "Dividend" });

    rerender(<TransactionFilters filters={{ ...EMPTY_FILTERS, type: "Dividend" }} onChange={onChange} brokers={[]} />);
    expect(screen.getByRole("button", { name: "Dividends" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Dividends" }));
    expect(onChange).toHaveBeenLastCalledWith(EMPTY_FILTERS);
  });

  it("keeps broker and dates in a sheet, applied together, and counts them on the button", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<TransactionFilters filters={EMPTY_FILTERS} onChange={onChange} brokers={["Trading 212", "DEGIRO"]} />);
    await userEvent.click(screen.getByRole("button", { name: /Filter/ }));
    await userEvent.selectOptions(screen.getByLabelText("Broker"), "DEGIRO");
    expect(onChange).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Show results" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY_FILTERS, broker: "DEGIRO" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    rerender(<TransactionFilters filters={{ ...EMPTY_FILTERS, broker: "DEGIRO" }} onChange={onChange} brokers={["DEGIRO"]} />);
    expect(screen.getByRole("button", { name: /Filter\s*1/ })).toBeInTheDocument();
  });
});
