import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryError } from "./QueryError";

describe("QueryError", () => {
  it("announces the message and retries on click", () => {
    const onRetry = vi.fn();
    render(<QueryError message="Couldn't load transactions." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load transactions.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("uses the module's own retry label", () => {
    render(<QueryError message="Lijsten laden mislukt." onRetry={() => {}} retryLabel="Opnieuw" />);
    expect(screen.getByRole("button", { name: "Opnieuw" })).toBeInTheDocument();
  });

  it("has no button without a retry", () => {
    render(<QueryError message="Couldn't load." />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
