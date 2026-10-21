import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LanguageProvider } from "../hooks/useLanguage";
import { setCurrentLanguage, t } from "../i18n";
import LanguagePicker from "./LanguagePicker";

function Heading() {
  return <h1>{t("Settings")}</h1>;
}

function renderPicker() {
  return render(
    <LanguageProvider>
      <Heading />
      <LanguagePicker />
    </LanguageProvider>,
  );
}

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("lang");
  vi.unstubAllGlobals();
  setCurrentLanguage("source");
});

describe("LanguagePicker", () => {
  it("starts in the browser's language when nothing is stored", () => {
    vi.stubGlobal("navigator", { ...navigator, language: "nl-NL" });
    renderPicker();
    expect(screen.getByRole("radio", { name: /Nederlands/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("heading")).toHaveTextContent("Instellingen");
    expect(document.documentElement.lang).toBe("nl");
  });

  it("falls back to English for any other browser language", () => {
    vi.stubGlobal("navigator", { ...navigator, language: "de-DE" });
    renderPicker();
    expect(screen.getByRole("radio", { name: /^English/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("heading")).toHaveTextContent("Settings");
  });

  it("switches the whole app at once and remembers the choice", async () => {
    localStorage.setItem("pdt-language", "en");
    renderPicker();
    await userEvent.click(screen.getByRole("radio", { name: /Nederlands/ }));
    expect(screen.getByRole("heading")).toHaveTextContent("Instellingen");
    expect(screen.getByRole("radio", { name: /Nederlands/ })).toHaveAttribute("aria-checked", "true");
    expect(localStorage.getItem("pdt-language")).toBe("nl");
    expect(document.documentElement.lang).toBe("nl");
  });

  it("ignores a stored value it doesn't know", () => {
    localStorage.setItem("pdt-language", "fr");
    vi.stubGlobal("navigator", { ...navigator, language: "en-GB" });
    renderPicker();
    expect(screen.getByRole("radio", { name: /^English/ })).toHaveAttribute("aria-checked", "true");
  });
});
