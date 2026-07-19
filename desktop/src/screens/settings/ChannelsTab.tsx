import { useState } from "react";
import { api } from "../../api/client";
import type { FullConfig } from "../../api/types";
import { AlertIcon } from "../../components/icons";
import {
  Button,
  Field,
  Panel,
  PanelBody,
  PanelHeader,
  TextInput,
  Toggle,
} from "../../design/primitives";
import p from "../page.module.css";
import { saveLabel, useSection } from "./useSection";

/** Restart-required banner — shared by Telegram and Server. */
export function RestartNotice({ what }: { what: string }) {
  return (
    <div className={p.notice}>
      <span className={p.noticeIcon}>
        <AlertIcon size={14} />
      </span>
      <span>
        {what} changes are written immediately but do <strong>not</strong> apply to the
        running process. Restart the backend for them to take effect.
      </span>
    </div>
  );
}

export function TelegramTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const { draft, set, dirty, saving, commit } = useSection(
    config.telegram,
    api.updateTelegram,
    onSaved,
  );
  const [token, setToken] = useState("");

  const save = () => {
    const patch: Record<string, unknown> = { ...draft };
    if (token.trim()) patch.bot_token = token.trim();
    void commit(patch).then(() => setToken(""));
  };

  const tokenDirty = token.trim().length > 0;

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="Telegram"
          subtitle="Long-polling bot — bidirectional, no public URL needed"
          actions={
            <Button
              size="sm"
              variant="primary"
              loading={saving}
              disabled={(!dirty && !tokenDirty) || saving}
              onClick={save}
            >
              {saveLabel(dirty || tokenDirty, saving)}
            </Button>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <Field label="Enabled">
              {(id) => (
                <Toggle
                  id={id}
                  checked={draft.enabled}
                  onChange={(v) => set("enabled", v)}
                />
              )}
            </Field>

            <Field
              label="Bot token"
              description={
                draft.has_token
                  ? "Configured. Leave blank to keep the stored token."
                  : "From @BotFather."
              }
            >
              {(id) => (
                <TextInput
                  id={id}
                  type="password"
                  value={token}
                  placeholder={draft.has_token ? "••••••••" : "123456:ABC-…"}
                  onChange={(e) => setToken(e.target.value)}
                />
              )}
            </Field>

            <Field
              label="Allowed user IDs"
              description="Comma separated numeric Telegram IDs. Empty means nobody can reach the bot."
            >
              {(id) => (
                <TextInput
                  id={id}
                  value={draft.allowed_user_ids.join(", ")}
                  onChange={(e) =>
                    set(
                      "allowed_user_ids",
                      e.target.value
                        .split(",")
                        .map((v) => Number(v.trim()))
                        .filter((v) => Number.isFinite(v) && v !== 0),
                    )
                  }
                />
              )}
            </Field>

            <Field
              label="Respond with audio"
              description="Send a voice note alongside the text reply."
            >
              {(id) => (
                <Toggle
                  id={id}
                  checked={draft.respond_with_audio}
                  onChange={(v) => set("respond_with_audio", v)}
                />
              )}
            </Field>

            <RestartNotice what="Telegram" />
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}

export function WhatsAppTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const { draft, set, dirty, saving, commit } = useSection(
    config.whatsapp,
    api.updateWhatsApp,
    onSaved,
  );
  const [apiKey, setApiKey] = useState("");

  const save = () => {
    const patch: Record<string, unknown> = { ...draft };
    if (apiKey.trim()) patch.evolution_api_key = apiKey.trim();
    void commit(patch).then(() => setApiKey(""));
  };

  const keyDirty = apiKey.trim().length > 0;

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="WhatsApp"
          subtitle="Via an Evolution API instance"
          actions={
            <Button
              size="sm"
              variant="primary"
              loading={saving}
              disabled={(!dirty && !keyDirty) || saving}
              onClick={save}
            >
              {saveLabel(dirty || keyDirty, saving)}
            </Button>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <Field label="Enabled">
              {(id) => (
                <Toggle
                  id={id}
                  checked={draft.enabled}
                  onChange={(v) => set("enabled", v)}
                />
              )}
            </Field>

            <div className={p.row2}>
              <Field label="Evolution API URL">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.evolution_api_url}
                    placeholder="http://localhost:8080"
                    onChange={(e) => set("evolution_api_url", e.target.value)}
                  />
                )}
              </Field>
              <Field label="Instance name">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.evolution_api_instance}
                    onChange={(e) => set("evolution_api_instance", e.target.value)}
                  />
                )}
              </Field>
            </div>

            <Field
              label="API key"
              description={
                draft.has_api_key
                  ? "Configured. Leave blank to keep the stored key."
                  : "The Evolution instance's API key."
              }
            >
              {(id) => (
                <TextInput
                  id={id}
                  type="password"
                  value={apiKey}
                  placeholder={draft.has_api_key ? "••••••••" : ""}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              )}
            </Field>

            <Field label="Respond with audio">
              {(id) => (
                <Toggle
                  id={id}
                  checked={draft.respond_with_audio}
                  onChange={(v) => set("respond_with_audio", v)}
                />
              )}
            </Field>
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}

export function ServerTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const { draft, set, dirty, saving, commit } = useSection(
    config.web,
    api.updateWeb,
    onSaved,
  );

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="HTTP server"
          subtitle="Where the backend binds and who may call it"
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
              <Field label="Host">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.host}
                    onChange={(e) => set("host", e.target.value)}
                  />
                )}
              </Field>
              <Field label="Port">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    value={draft.port}
                    onChange={(e) => set("port", Number(e.target.value))}
                  />
                )}
              </Field>
            </div>

            <Field
              label="Expose on the LAN"
              description="Binds 0.0.0.0 instead of loopback. Only do this behind a trusted network."
            >
              {(id) => (
                <Toggle
                  id={id}
                  checked={draft.expose_lan}
                  onChange={(v) => set("expose_lan", v)}
                />
              )}
            </Field>

            <Field
              label="CORS origins"
              description="Comma separated. The desktop app needs tauri://localhost and http://tauri.localhost here."
            >
              {(id) => (
                <TextInput
                  id={id}
                  value={draft.cors_origins.join(", ")}
                  onChange={(e) =>
                    set(
                      "cors_origins",
                      e.target.value
                        .split(",")
                        .map((v) => v.trim())
                        .filter(Boolean),
                    )
                  }
                />
              )}
            </Field>

            <RestartNotice what="Host and port" />
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
