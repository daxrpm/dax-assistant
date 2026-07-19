import { api } from "../../api/client";
import type { FullConfig } from "../../api/types";
import {
  Badge,
  Button,
  Field,
  Panel,
  PanelBody,
  PanelHeader,
  Select,
  TextArea,
  TextInput,
} from "../../design/primitives";
import p from "../page.module.css";
import { saveLabel, useSection } from "./useSection";

const LANGUAGES = [
  { value: "auto", label: "Auto-detect" },
  { value: "es", label: "Spanish" },
  { value: "en", label: "English" },
];

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

export function GeneralTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const { draft, set, setDraft, dirty, saving, commit } = useSection(
    config.general,
    api.updateGeneral,
    onSaved,
  );

  const resetPrompt = async () => {
    const result = await api.resetSystemPrompt();
    setDraft({ ...draft, system_prompt: result.system_prompt, system_prompt_custom: false });
    onSaved();
  };

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="Identity"
          subtitle="How the assistant introduces and behaves by default"
          actions={
            <Button
              size="sm"
              variant="primary"
              loading={saving}
              disabled={!dirty || saving}
              onClick={() => void commit()}
            >
              {saveLabel(dirty, saving)}
            </Button>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <Field label="Assistant name">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.name}
                    onChange={(e) => set("name", e.target.value)}
                  />
                )}
              </Field>
              <Field label="Default language">
                {(id) => (
                  <Select
                    id={id}
                    value={draft.language_default}
                    onChange={(e) => set("language_default", e.target.value)}
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l.value} value={l.value}>
                        {l.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>

            <div className={p.row2}>
              <Field label="Log level">
                {(id) => (
                  <Select
                    id={id}
                    value={draft.log_level}
                    onChange={(e) => set("log_level", e.target.value)}
                  >
                    {LOG_LEVELS.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Memory path" description="Read-only — set at install time.">
                {(id) => <TextInput id={id} value={draft.memory_path} readOnly />}
              </Field>
            </div>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="System prompt"
          subtitle={
            draft.system_prompt_custom ? undefined : "Currently the shipped default"
          }
          actions={
            <div className={p.actions}>
              {draft.system_prompt_custom && <Badge tone="accent">Customized</Badge>}
              <Button size="sm" variant="ghost" onClick={() => void resetPrompt()}>
                Reset to default
              </Button>
            </div>
          }
        />
        <PanelBody>
          <Field description="Applies to every channel. Saved with the section above.">
            {(id) => (
              <TextArea
                id={id}
                rows={14}
                value={draft.system_prompt}
                onChange={(e) => set("system_prompt", e.target.value)}
              />
            )}
          </Field>
        </PanelBody>
      </Panel>
    </div>
  );
}
