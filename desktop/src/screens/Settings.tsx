import { useDeferredValue, useState } from "react";
import {
  BrainIcon,
  ChatIcon,
  McpIcon,
  SearchIcon,
  SettingsIcon,
  ShieldIcon,
  SparkleIcon,
  VoiceIcon,
  WrenchIcon,
  XIcon,
} from "../components/icons";
import { Button, Panel, PanelBody, Spinner } from "../design/primitives";
import { cn } from "../lib/cn";
import { useConfig } from "../hooks/useConfig";
import { useTheme } from "../lib/useTheme";
import { useI18n } from "../i18n/I18n";
import p from "./page.module.css";
import { sectionsForLocale, searchGroups } from "./settings/registry";
import {
  SettingsGroup,
  SettingsSection,
  type RendererContext,
} from "./settings/SettingsRenderer";
import s from "./settings/settings.module.css";
import { useSettingsDraft } from "./settings/useSettingsDraft";

const SECTION_ICONS = {
  voz: <VoiceIcon size={15} />,
  inteligencia: <SparkleIcon size={15} />,
  capacidades: <WrenchIcon size={15} />,
  memoria: <BrainIcon size={15} />,
  canales: <ChatIcon size={15} />,
  acceso: <ShieldIcon size={15} />,
  sistema: <SettingsIcon size={15} />,
} as const;

function SettingsContent() {
  const { t } = useI18n();
  const { config, loading, error, refresh } = useConfig();
  const { mode, setMode } = useTheme();

  if (loading && !config) {
    return <div className={s.state}><Spinner size={20} /></div>;
  }

  if (!config) {
    return (
      <Panel>
        <PanelBody>
          <div className={s.errorState}>
            <strong>{t("settings.loadFailed")}</strong>
            <span>{error ?? t("settings.backendNoResponse")}</span>
            <Button variant="secondary" onClick={() => void refresh()}>{t("common.retry")}</Button>
          </div>
        </PanelBody>
      </Panel>
    );
  }

  return (
    <LoadedSettings
      config={config}
      error={error}
      refresh={refresh}
      themeMode={mode}
      onThemeChange={setMode}
    />
  );
}

function LoadedSettings({
  config,
  error,
  refresh,
  themeMode,
  onThemeChange,
}: {
  config: NonNullable<ReturnType<typeof useConfig>["config"]>;
  error: string | null;
  refresh: () => Promise<void>;
  themeMode: ReturnType<typeof useTheme>["mode"];
  onThemeChange: ReturnType<typeof useTheme>["setMode"];
}) {
  const { locale, t } = useI18n();
  const sections = sectionsForLocale(locale);
  const [activeId, setActiveId] = useState(sections[0]?.id ?? "voz");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim());
  const draft = useSettingsDraft(config, refresh);
  const active = sections.find((section) => section.id === activeId) ?? sections[0];
  const hits = deferredSearch ? searchGroups(deferredSearch, sections) : [];
  const context: RendererContext = {
    config,
    draft,
    onSaved: refresh,
    themeMode,
    onThemeChange,
  };

  return (
    <>
      {error && (
        <div className={s.loadError} role="alert">
          <span>{error}</span>
          <Button size="sm" variant="ghost" onClick={() => void refresh()}>{t("common.retry")}</Button>
        </div>
      )}

      <div className={s.search}>
        <span className={s.searchIcon}><SearchIcon size={15} /></span>
        <input
          className={s.searchInput}
          type="search"
          value={search}
          placeholder={t("settings.search")}
          aria-label={t("settings.search")}
          onChange={(event) => setSearch(event.target.value)}
        />
        {search && (
          <button className={s.searchClear} type="button" aria-label={t("settings.clearSearch")} onClick={() => setSearch("")}>
            <XIcon size={13} />
          </button>
        )}
      </div>

      <div className={s.shell}>
        <nav className={s.rail} aria-label={t("settings.sections")}>
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              className={cn(s.railItem, !deferredSearch && section.id === active?.id && s.railItemActive)}
              aria-current={!deferredSearch && section.id === active?.id ? "page" : undefined}
              onClick={() => {
                setActiveId(section.id);
                setSearch("");
              }}
            >
              <span className={s.railIcon}>
                {SECTION_ICONS[section.id as keyof typeof SECTION_ICONS] ?? <McpIcon size={15} />}
              </span>
              {section.title}
            </button>
          ))}
        </nav>

        {deferredSearch ? (
          <section className={s.results} aria-live="polite">
            <div className={s.sectionHead}>
              <h2 className={s.sectionTitle}>{t("settings.results")}</h2>
              <span className={s.resultsCount}>
                {t("settings.groups", { count: hits.length })}
              </span>
            </div>
            {hits.length === 0 ? (
              <Panel><PanelBody>{t("settings.noMatch", { query: deferredSearch })}</PanelBody></Panel>
            ) : (
              hits.map(({ section, group, fields }) => (
                <div key={`${section.id}:${group.id}`} className={s.result}>
                  <div className={s.breadcrumb}>
                    <button
                      type="button"
                      className={s.breadcrumbLink}
                      onClick={() => {
                        setActiveId(section.id);
                        setSearch("");
                      }}
                    >
                      {section.title}
                    </button>
                    <span>/</span>
                    <span>{group.title}</span>
                  </div>
                  <SettingsGroup group={group} fields={fields} context={context} searching />
                </div>
              ))
            )}
          </section>
        ) : active ? (
          <SettingsSection section={active} context={context} />
        ) : null}
      </div>
    </>
  );
}

export function Settings() {
  const { t } = useI18n();
  return (
    <div className={p.scrollPage}>
      <div className={cn(p.page, s.settingsPage)}>
        <div className={p.pageHead}>
          <div className={p.pageMark}><SettingsIcon size={19} /></div>
          <div>
            <h1 className={p.pageTitle}>{t("settings.title")}</h1>
            <p className={p.pageSubtitle}>{t("settings.subtitle")}</p>
          </div>
        </div>
        <SettingsContent />
      </div>
    </div>
  );
}
