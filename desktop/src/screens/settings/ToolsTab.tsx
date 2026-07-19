import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { FullConfig, ToolPolicyResponse } from "../../api/types";
import { AlertIcon } from "../../components/icons";
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
  Toggle,
  useToast,
} from "../../design/primitives";
import p from "../page.module.css";
import { saveLabel, useSection } from "./useSection";

const DECISIONS = ["allow", "ask", "deny"];

/** Newline-separated text ⇄ pattern list. */
function toLines(list: string[]): string {
  return list.join("\n");
}

function fromLines(text: string): string[] {
  return text
    .split("\n")
    .map((v) => v.trim())
    .filter(Boolean);
}

function ChangePassword() {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  const tooShort = next.length > 0 && next.length < 8;
  const mismatch = confirm.length > 0 && next !== confirm;
  const canSubmit = current && next.length >= 8 && next === confirm && !saving;

  const submit = async () => {
    setSaving(true);
    try {
      await api.changePassword(current, next);
      toast.show("Password changed", "success");
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Change failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Password"
        actions={
          <Button
            size="sm"
            variant="primary"
            loading={saving}
            disabled={!canSubmit}
            onClick={() => void submit()}
          >
            Change password
          </Button>
        }
      />
      <PanelBody>
        <div className={p.rows}>
          <Field label="Current password">
            {(id) => (
              <TextInput
                id={id}
                type="password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            )}
          </Field>
          <div className={p.row2}>
            <Field
              label="New password"
              error={tooShort ? "At least 8 characters." : undefined}
            >
              {(id) => (
                <TextInput
                  id={id}
                  type="password"
                  value={next}
                  invalid={tooShort}
                  onChange={(e) => setNext(e.target.value)}
                />
              )}
            </Field>
            <Field
              label="Confirm new password"
              error={mismatch ? "Passwords do not match." : undefined}
            >
              {(id) => (
                <TextInput
                  id={id}
                  type="password"
                  value={confirm}
                  invalid={mismatch}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              )}
            </Field>
          </div>
        </div>
      </PanelBody>
    </Panel>
  );
}

export function ToolsTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const tools = useSection(config.tools, api.updateTools, onSaved);
  const security = useSection(config.security, api.updateSecurity, onSaved);
  const [live, setLive] = useState<ToolPolicyResponse | null>(null);

  // The live policy is what the running agent actually enforces; showing it
  // next to the editable config surfaces drift after a failed reload.
  useEffect(() => {
    api
      .toolPolicy()
      .then(setLive)
      .catch(() => setLive(null));
  }, [config]);

  const policy = tools.draft.policy;
  const setPolicy = (patch: Partial<typeof policy>) =>
    tools.set("policy", { ...policy, ...patch });

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="Tool policy"
          subtitle="Applies live — no restart needed"
          actions={
            <div className={p.actions}>
              {live && <Badge tone="neutral">{live.ask.length} ask rules active</Badge>}
              <Button
                size="sm"
                variant="primary"
                loading={tools.saving}
                disabled={!tools.dirty || tools.saving}
                onClick={() => void tools.commit()}
              >
                {saveLabel(tools.dirty, tools.saving)}
              </Button>
            </div>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <Field
                label="Default decision"
                description="Applied to any tool no pattern matches."
              >
                {(id) => (
                  <Select
                    id={id}
                    value={policy.default}
                    onChange={(e) => setPolicy({ default: e.target.value })}
                  >
                    {DECISIONS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field
                label="Confirmation timeout (seconds)"
                description="Unanswered prompts are DENIED when this elapses."
              >
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    value={tools.draft.confirm_timeout_seconds}
                    onChange={(e) =>
                      tools.set("confirm_timeout_seconds", Number(e.target.value))
                    }
                  />
                )}
              </Field>
            </div>

            <Field
              label="Allow"
              description="One pattern per line. These run without asking."
            >
              {(id) => (
                <TextArea
                  id={id}
                  rows={4}
                  value={toLines(policy.allow)}
                  onChange={(e) => setPolicy({ allow: fromLines(e.target.value) })}
                />
              )}
            </Field>

            <Field
              label="Ask"
              description="These raise the confirmation prompt in chat."
            >
              {(id) => (
                <TextArea
                  id={id}
                  rows={4}
                  value={toLines(policy.ask)}
                  onChange={(e) => setPolicy({ ask: fromLines(e.target.value) })}
                />
              )}
            </Field>

            <Field label="Deny" description="These are refused outright.">
              {(id) => (
                <TextArea
                  id={id}
                  rows={4}
                  value={toLines(policy.deny)}
                  onChange={(e) => setPolicy({ deny: fromLines(e.target.value) })}
                />
              )}
            </Field>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Security"
          actions={
            <Button
              size="sm"
              variant="primary"
              loading={security.saving}
              disabled={!security.dirty || security.saving}
              onClick={() => void security.commit()}
            >
              {saveLabel(security.dirty, security.saving)}
            </Button>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.spread}>
              <Field
                label="Require login"
                description="Disabling this leaves the API open to anything that can reach the port."
              >
                {(id) => (
                  <Toggle
                    id={id}
                    checked={security.draft.auth_enabled}
                    onChange={(v) => security.set("auth_enabled", v)}
                  />
                )}
              </Field>
              <Field
                label="Secure cookie"
                description="Requires HTTPS. Leave off for plain-HTTP loopback."
              >
                {(id) => (
                  <Toggle
                    id={id}
                    checked={security.draft.cookie_secure}
                    onChange={(v) => security.set("cookie_secure", v)}
                  />
                )}
              </Field>
            </div>

            <Field label="Session lifetime (hours)">
              {(id) => (
                <TextInput
                  id={id}
                  type="number"
                  value={security.draft.session_ttl_hours}
                  onChange={(e) =>
                    security.set("session_ttl_hours", Number(e.target.value))
                  }
                />
              )}
            </Field>

            {!security.draft.auth_enabled && (
              <div className={p.notice}>
                <span className={p.noticeIcon}>
                  <AlertIcon size={14} />
                </span>
                <span>
                  With login disabled, anyone who can reach this host can drive the
                  assistant and every tool it holds.
                </span>
              </div>
            )}
          </div>
        </PanelBody>
      </Panel>

      <ChangePassword />
    </div>
  );
}
