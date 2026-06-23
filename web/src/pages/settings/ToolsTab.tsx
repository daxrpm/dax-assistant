import { useState } from "react";
import { Button } from "@heroui/react";
import { api } from "../../api/client";
import type { FullConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  TextArea,
  Select,
  Toggle,
  Badge,
  useToast,
} from "../../components/ui";

const toLines = (arr: string[]) => arr.join("\n");
const fromLines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

export function ToolsTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const policy = config.tools.policy;
  const [defaultPolicy, setDefaultPolicy] = useState(policy.default);
  const [allow, setAllow] = useState(toLines(policy.allow));
  const [ask, setAsk] = useState(toLines(policy.ask));
  const [deny, setDeny] = useState(toLines(policy.deny));
  const [timeout, setTimeout] = useState(config.tools.confirm_timeout_seconds);

  const sec = config.security;
  const [authEnabled, setAuthEnabled] = useState(sec.auth_enabled);
  const [cookieSecure, setCookieSecure] = useState(sec.cookie_secure);
  const [ttl, setTtl] = useState(sec.session_ttl_hours);
  const [saving, setSaving] = useState(false);

  // Password change state
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwSaving, setPwSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateTools({
        confirm_timeout_seconds: timeout,
        policy: {
          default: defaultPolicy,
          allow: fromLines(allow),
          ask: fromLines(ask),
          deny: fromLines(deny),
        },
      });
      await api.updateSecurity({
        auth_enabled: authEnabled,
        cookie_secure: cookieSecure,
        session_ttl_hours: ttl,
      });
      toast.show("Security & tools saved", "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async () => {
    if (newPw.length < 8) {
      toast.show("Password must be at least 8 characters", "warning");
      return;
    }
    if (newPw !== confirmPw) {
      toast.show("Passwords do not match", "warning");
      return;
    }
    setPwSaving(true);
    try {
      await api.changePassword(currentPw, newPw);
      toast.show("Password changed — auth is now enabled", "success");
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      setAuthEnabled(true);
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Failed to change password", "danger");
    } finally {
      setPwSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Panel>
        <PanelHeader
          title="Tool policy"
          description="Control which tools run freely, need confirmation, or are blocked"
        />
        <div className="flex flex-col gap-4">
          <Field
            label="Default decision"
            description="Applied to tools that match none of the lists below"
          >
            <Select
              value={defaultPolicy}
              onChange={(e) => setDefaultPolicy(e.target.value)}
            >
              <option value="allow">Allow</option>
              <option value="ask">Ask for confirmation</option>
              <option value="deny">Deny</option>
            </Select>
          </Field>
          <Field
            label="Ask patterns"
            description="fnmatch globs that require confirmation (one per line). Empty = built-in destructive defaults."
          >
            <TextArea
              rows={3}
              value={ask}
              onChange={(e) => setAsk(e.target.value)}
              placeholder="*write*&#10;*delete*&#10;*shell*"
            />
          </Field>
          <Field label="Allow patterns" description="Always run without asking (one per line)">
            <TextArea
              rows={2}
              value={allow}
              onChange={(e) => setAllow(e.target.value)}
              placeholder="fs_read&#10;system_info"
            />
          </Field>
          <Field label="Deny patterns" description="Never run (one per line)">
            <TextArea
              rows={2}
              value={deny}
              onChange={(e) => setDeny(e.target.value)}
              placeholder="*format_disk*"
            />
          </Field>
          <Field label="Confirmation timeout (seconds)">
            <TextInput
              type="number"
              value={timeout}
              onChange={(e) => setTimeout(Number(e.target.value))}
            />
          </Field>
        </div>
      </Panel>

      <Panel>
        <PanelHeader
          title="Security"
          description="Session, authentication and login"
          action={
            <Badge color={authEnabled ? "success" : "warning"}>
              {authEnabled ? "Auth on" : "Auth off"}
            </Badge>
          }
        />
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
            <div>
              <p className="text-sm font-medium">Require login</p>
              <p className="text-xs text-muted">
                Protect the web UI with a password. Requires a password to be set below.
              </p>
            </div>
            <Toggle
              checked={authEnabled}
              onChange={setAuthEnabled}
              label="Require login"
              disabled={!sec.configured && !authEnabled}
            />
          </div>
          <Field label="Session lifetime (hours)">
            <TextInput
              type="number"
              value={ttl}
              onChange={(e) => setTtl(Number(e.target.value))}
            />
          </Field>
          <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
            <div>
              <p className="text-sm font-medium">Secure cookie</p>
              <p className="text-xs text-muted">
                Mark the session cookie Secure (HTTPS only)
              </p>
            </div>
            <Toggle
              checked={cookieSecure}
              onChange={setCookieSecure}
              label="Secure cookie"
            />
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHeader
          title="Change password"
          description={
            sec.configured
              ? "Update the login password"
              : "Set a password to enable authentication"
          }
        />
        <div className="flex flex-col gap-4">
          {sec.configured && (
            <Field label="Current password">
              <TextInput
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                autoComplete="current-password"
              />
            </Field>
          )}
          <Field label="New password" description="Minimum 8 characters">
            <TextInput
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Confirm new password">
            <TextInput
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              autoComplete="new-password"
            />
          </Field>
          <div className="flex justify-end">
            <Button
              variant="primary"
              onPress={changePassword}
              isDisabled={pwSaving || !newPw || newPw !== confirmPw}
            >
              {pwSaving ? "Saving…" : sec.configured ? "Update password" : "Set password"}
            </Button>
          </div>
        </div>
      </Panel>

      <div className="flex justify-end">
        <Button variant="primary" onPress={save} isDisabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  );
}
