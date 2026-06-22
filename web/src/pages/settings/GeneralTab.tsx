import { useState } from "react";
import { Button } from "@heroui/react";
import { api } from "../../api/client";
import type { FullConfig } from "../../types/config";
import { Panel, PanelHeader, Field, TextInput, Select } from "../../components/ui";
import { useToast } from "../../components/ui";

export function GeneralTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(config.general.name);
  const [lang, setLang] = useState(config.general.language_default);
  const [logLevel, setLogLevel] = useState(config.general.log_level);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateGeneral({
        name,
        language_default: lang,
        log_level: logLevel,
      });
      toast.show("General settings saved", "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="General" description="Assistant identity and logging" />
      <div className="flex flex-col gap-4">
        <Field label="Assistant name">
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Default language">
          <Select value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="es">Spanish</option>
            <option value="en">English</option>
            <option value="auto">Auto-detect</option>
          </Select>
        </Field>
        <Field label="Log level">
          <Select value={logLevel} onChange={(e) => setLogLevel(e.target.value)}>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </Select>
        </Field>
        <div className="flex justify-end">
          <Button variant="primary" onPress={save} isDisabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
