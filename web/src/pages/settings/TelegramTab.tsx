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

export function TelegramTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const t = config.telegram;
  const [enabled, setEnabled] = useState(t.enabled);
  const [token, setToken] = useState("");
  const [allowedIds, setAllowedIds] = useState(t.allowed_user_ids.join(", "));
  const [respondAudio, setRespondAudio] = useState(t.respond_with_audio);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const ids = allowedIds
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !Number.isNaN(n));
      const payload: Record<string, unknown> = {
        enabled,
        allowed_user_ids: ids,
        respond_with_audio: respondAudio,
      };
      if (token) payload.bot_token = token;
      await api.updateTelegram(payload);
      setToken("");
      toast.show("Telegram settings saved and applied", "success");
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
        title="Telegram"
        description="Personal bot via long-polling — no public URL needed"
        action={
          <Badge color={t.has_token ? "success" : "default"}>
            {t.has_token ? "Token set" : "No token"}
          </Badge>
        }
      />
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Enable Telegram</p>
            <p className="text-xs text-muted">Chat with Dax from Telegram</p>
          </div>
          <Toggle checked={enabled} onChange={setEnabled} label="Telegram enabled" />
        </div>
        <Field
          label="Bot token"
          description="Create a bot with @BotFather and paste its token. Leave blank to keep current."
        >
          <TextInput
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="123456:ABC-DEF1234ghIkl…"
          />
        </Field>
        <Field
          label="Allowed user IDs"
          description="Comma-separated numeric Telegram user IDs. Empty = anyone who messages the bot. Use @userinfobot to find yours."
        >
          <TextInput
            value={allowedIds}
            onChange={(e) => setAllowedIds(e.target.value)}
            placeholder="123456789, 987654321"
          />
        </Field>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Reply with audio</p>
            <p className="text-xs text-muted">Send TTS voice notes (when available)</p>
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
