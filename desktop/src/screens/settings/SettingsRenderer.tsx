import { useState, type ReactNode } from "react";
import { api } from "../../api/client";
import type { FullConfig } from "../../api/types";
import { McpServers } from "../../components/McpServers";
import { ChevronRightIcon } from "../../components/icons";
import { Button, Panel, PanelBody, PanelHeader, useToast } from "../../design/primitives";
import { cn } from "../../lib/cn";
import type { ThemeMode } from "../../lib/useTheme";
import { useI18n } from "../../i18n/I18n";
import { Commands } from "../Commands";
import p from "../page.module.css";
import { DesktopTab } from "./DesktopTab";
import { FieldControl } from "./FieldControl";
import { MemoryTab } from "./MemoryTab";
import type { FieldSpec, GroupSpec, SectionSpec } from "./registry";
import s from "./settings.module.css";
import { ChangePassword } from "./ToolsTab";
import type { SettingsDraft } from "./useSettingsDraft";
import { VoiceEnrollment } from "./VoiceEnrollment";
import { VoiceStatus } from "./VoiceStatus";

interface RendererContext {
  config: FullConfig;
  draft: SettingsDraft;
  onSaved: () => void;
  themeMode: ThemeMode;
  onThemeChange: (next: ThemeMode) => void;
}

function CustomGroup({ group, context }: { group: GroupSpec; context: RendererContext }) {
  switch (group.custom) {
    case "voice-status":
      return <VoiceStatus config={context.config} />;
    case "voice-enrollment":
      return <VoiceEnrollment />;
    case "mcp-servers":
      return <McpServers config={context.config} onSaved={context.onSaved} />;
    case "shell-allow":
      return (
        <div className={s.embeddedPage}>
          <Commands />
        </div>
      );
    case "memory-files":
      return <MemoryTab />;
    case "change-password":
      return <ChangePassword />;
    case "desktop":
      return (
        <DesktopTab
          themeMode={context.themeMode}
          onThemeChange={context.onThemeChange}
        />
      );
    default:
      return null;
  }
}

function GeneratedGroup({
  group,
  fields,
  context,
  searching,
}: {
  group: GroupSpec;
  fields: FieldSpec[];
  context: RendererContext;
  searching: boolean;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [open, setOpen] = useState(!group.collapsible);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [resettingPrompt, setResettingPrompt] = useState(false);
  const visibleOpen = searching || open;
  const normal = fields.filter((field) => !field.advanced);
  const advanced = fields.filter((field) => field.advanced);
  const dirty = context.draft.groupDirty(group);
  const saving = context.draft.savingGroup === group.id;

  const resetPrompt = async () => {
    setResettingPrompt(true);
    try {
      await api.resetSystemPrompt();
      context.draft.resetGroup(group);
      context.onSaved();
      toast.show(t("settings.promptRestored"), "success");
    } catch (error) {
      toast.show(error instanceof Error ? error.message : t("settings.restoreFailed"), "danger");
    } finally {
      setResettingPrompt(false);
    }
  };

  const title: ReactNode = group.collapsible && !searching ? (
    <button className={s.groupToggle} type="button" onClick={() => setOpen((value) => !value)}>
      <span className={cn(s.groupChevron, visibleOpen && s.groupChevronOpen)}>
        <ChevronRightIcon size={14} />
      </span>
      {group.title}
    </button>
  ) : (
    group.title
  );

  return (
    <Panel>
      <PanelHeader
        title={title}
        subtitle={group.description}
        actions={
          <div className={p.actions}>
            {group.custom === "system-prompt" && (
              <Button
                size="sm"
                variant="ghost"
                loading={resettingPrompt}
                disabled={resettingPrompt || saving}
                onClick={() => void resetPrompt()}
              >
                {t("settings.restorePrompt")}
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              disabled={!dirty || saving}
              onClick={() => context.draft.resetGroup(group)}
            >
              {t("settings.discard")}
            </Button>
            <Button
              size="sm"
              variant="primary"
              loading={saving}
              disabled={!dirty || saving}
              onClick={() => void context.draft.saveGroup(group)}
            >
              {saving ? t("common.saving") : dirty ? t("common.saveChanges") : t("common.saved")}
            </Button>
          </div>
        }
      />
      {visibleOpen && (
        <PanelBody>
          <div className={s.fields}>
            {normal.map((field) => (
              <FieldControl key={`${field.key}:${field.path}`} field={field} draft={context.draft} />
            ))}
            {advanced.length > 0 && !searching && (
              <button
                className={s.advancedToggle}
                type="button"
                onClick={() => setAdvancedOpen((value) => !value)}
              >
                <ChevronRightIcon size={12} />
                {advancedOpen ? t("settings.hideAdvanced") : t("settings.showAdvanced")}
                <span className={s.advancedCount}>{advanced.length}</span>
              </button>
            )}
            {(searching || advancedOpen) && advanced.length > 0 && (
              <div className={s.advanced}>
                {advanced.map((field) => (
                  <FieldControl
                    key={`${field.key}:${field.path}`}
                    field={field}
                    draft={context.draft}
                  />
                ))}
              </div>
            )}
          </div>
        </PanelBody>
      )}
    </Panel>
  );
}

export function SettingsGroup({
  group,
  fields = group.fields,
  context,
  searching = false,
}: {
  group: GroupSpec;
  fields?: FieldSpec[];
  context: RendererContext;
  searching?: boolean;
}) {
  const generated = fields.filter((field) => field.control !== "custom");
  return (
    <div className={s.groupStack}>
      {group.custom && group.custom !== "system-prompt" && (
        <CustomGroup group={group} context={context} />
      )}
      {generated.length > 0 && (
        <GeneratedGroup
          group={group}
          fields={generated}
          context={context}
          searching={searching}
        />
      )}
    </div>
  );
}

export function SettingsSection({
  section,
  context,
}: {
  section: SectionSpec;
  context: RendererContext;
}) {
  return (
    <section className={s.section} aria-labelledby={`settings-${section.id}`}>
      <div className={s.sectionHead}>
        <h2 id={`settings-${section.id}`} className={s.sectionTitle}>{section.title}</h2>
        <p className={s.sectionDescription}>{section.description}</p>
      </div>
      {section.groups.map((group) => (
        <SettingsGroup key={group.id} group={group} context={context} />
      ))}
    </section>
  );
}

export type { RendererContext };
