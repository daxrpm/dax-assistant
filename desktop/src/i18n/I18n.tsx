import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { en, es, type MessageKey } from "./catalog";

export type Locale = "es" | "en";
export const LOCALE_STORAGE_KEY = "dax.ui.locale";

export function normalizeLocale(value: string | null | undefined): Locale | null {
  if (!value) return null;
  const language = value.trim().toLowerCase().split(/[-_]/)[0];
  return language === "es" || language === "en" ? language : null;
}

export function detectLocale(
  languages: readonly string[] = typeof navigator === "undefined"
    ? []
    : navigator.languages?.length ? navigator.languages : [navigator.language],
  stored?: string | null,
): Locale {
  if (stored === undefined && typeof localStorage !== "undefined") {
    try {
      stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    } catch {
      stored = null;
    }
  }
  const persisted = normalizeLocale(stored);
  if (persisted) return persisted;
  for (const language of languages) {
    const locale = normalizeLocale(language);
    if (locale) return locale;
  }
  return "es";
}

type Params = Record<string, string | number>;
export type Translate = (key: MessageKey, params?: Params) => string;

function format(message: string, params?: Params): string {
  if (!params) return message;
  return message.replace(/\{(\w+)\}/g, (match, key: string) =>
    Object.hasOwn(params, key) ? String(params[key]) : match,
  );
}

interface I18nValue {
  locale: Locale;
  intlLocale: "es-ES" | "en-US";
  setLocale: (locale: Locale) => void;
  t: Translate;
  text: (spanish: string, english: string) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children, initialLocale }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(() => initialLocale ?? detectLocale());

  const setLocale = (next: Locale) => {
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // The UI still changes when storage is blocked by the webview/browser.
    }
    setLocaleState(next);
  };

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18nValue>(() => {
    const catalog = locale === "en" ? en : es;
    return {
      locale,
      intlLocale: locale === "en" ? "en-US" : "es-ES",
      setLocale,
      t: (key, params) => format(catalog[key] ?? es[key] ?? key, params),
      text: (spanish, english) => locale === "en" ? english : spanish,
    };
  }, [locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside <I18nProvider>");
  return value;
}
