import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ModuleTopRow } from "./ui/kit";

vi.mock("./ModuleSwitcher", () => ({ default: () => null }));
vi.mock("./ModuleIndicators", () => ({ default: () => null }));
vi.mock("./GainrSettingsButton", () => ({ default: () => <button aria-label="Settings">gainr gear</button> }));
vi.mock("./gripr/GriprSettingsButton", () => ({ default: () => <button aria-label="Settings">gripr gear</button> }));

function renderRow(path: string, settings?: boolean) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ModuleTopRow settings={settings} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the top row's settings gear", () => {
  it.each([
    ["/gainr", "gainr gear"],
    ["/transactions", "gainr gear"],
    ["/gripr/transactions", "gripr gear"],
  ])("opens the module's own settings on %s", (path, label) => {
    renderRow(path);
    expect(screen.getByRole("button", { name: "Settings" })).toHaveTextContent(label);
  });

  it.each(["/listr/recepten", "/gardnr/vandaag", "/taskr", "/"])("opens the app-wide settings, with the font, on %s", async (path) => {
    renderRow(path);
    await userEvent.click(screen.getByRole("button", { name: "Settings" }));
    await userEvent.click(screen.getByRole("button", { name: /Font/ }));
    expect(screen.getByRole("radio", { name: /Manrope/ })).toBeInTheDocument();
  });

  it("can leave the gear out for a page that has it elsewhere", () => {
    renderRow("/gripr/budget", false);
    expect(screen.queryByRole("button", { name: "Settings" })).not.toBeInTheDocument();
  });
});
