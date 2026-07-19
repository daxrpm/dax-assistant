import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { I18nProvider, LOCALE_STORAGE_KEY, detectLocale, normalizeLocale, useI18n } from "./I18n";

function Probe() {
  const { locale, setLocale, t } = useI18n();
  return <button onClick={() => setLocale(locale === "es" ? "en" : "es")}>{t("settings.title")}</button>;
}

describe("i18n", () => {
  beforeEach(() => localStorage.clear());

  it("detects supported system languages and safely falls back", () => {
    expect(normalizeLocale("en-GB")).toBe("en");
    expect(detectLocale(["fr-FR", "en-US"], null)).toBe("en");
    expect(detectLocale(["fr-FR"], null)).toBe("es");
  });

  it("prefers a valid persisted locale and ignores invalid values", () => {
    expect(detectLocale(["es-ES"], "en")).toBe("en");
    expect(detectLocale(["en-US"], "xx")).toBe("en");
  });

  it("renders and persists a language change", () => {
    render(<I18nProvider initialLocale="es"><Probe /></I18nProvider>);
    const button = screen.getByRole("button", { name: "Ajustes" });
    fireEvent.click(button);
    expect(screen.getByRole("button", { name: "Settings" })).toBeTruthy();
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });
});
