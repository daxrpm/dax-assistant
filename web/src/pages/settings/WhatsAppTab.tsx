import { useState } from "react";
import { Button } from "@heroui/react";
import { api } from "../../api/client";
import type { FullConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  Toggle,
  Badge,
  useToast,
} from "../../components/ui";

export function WhatsAppTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const w = config.whatsapp;
  const [enabled, setEnabled] = useState(w.enabled);
  const [url, setUrl] = useState(w.evolution_api_url);
  const [instance, setInstance] = useState(w.evolution_api_instance);
  const [respondAudio, setRespondAudio] = useState(w.respond_with_audio);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        enabled,
        evolution_api_url: url,
        evolution_api_instance: instance,
        respond_with_audio: respondAudio,
      };
      if (apiKey) payload.evolution_api_key = apiKey;
      await api.updateWhatsApp(payload);
      toast.show("WhatsApp settings saved", "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="WhatsApp"
        description="Evolution API v2 integration"
        action={
          <Badge color={w.has_api_key ? "success" : "default"}>
            {w.has_api_key ? "Key configured" : "No key"}
          </Badge>
        }
      />
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Enable WhatsApp</p>
            <p className="text-xs text-muted">Receive and reply via Evolution API</p>
          </div>
          <Toggle checked={enabled} onChange={setEnabled} label="WhatsApp enabled" />
        </div>
        <Field label="Evolution API URL">
          <TextInput value={url} onChange={(e) => setUrl(e.target.value)} />
        </Field>
        <Field label="Instance">
          <TextInput value={instance} onChange={(e) => setInstance(e.target.value)} />
        </Field>
        <Field label="API key" description="Leave blank to keep the current key">
          <TextInput
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="••••••••"
          />
        </Field>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Reply with audio</p>
            <p className="text-xs text-muted">Send TTS voice notes</p>
          </div>
          <Toggle
            checked={respondAudio}
            onChange={setRespondAudio}
            label="Respond with audio"
          />
        </div>
        <div className="flex justify-end">
          <Button variant="primary" onPress={save} isDisabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
