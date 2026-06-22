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
  const [cookieSecure, setCookieSecure] = useState(sec.cookie_secure);
  const [ttl, setTtl] = useState(sec.session_ttl_hours);
  const [saving, setSaving] = useState(false);

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
          description="Session and authentication"
          action={
            <Badge color={sec.auth_enabled ? "success" : "warning"}>
              {sec.auth_enabled ? "Auth on" : "Auth off"}
            </Badge>
          }
        />
        <div className="flex flex-col gap-4">
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
          <p className="text-xs text-muted">
            The login password and session secret are set via environment variables
            (<code>DAX_SECURITY__PASSWORD_HASH</code>,{" "}
            <code>DAX_SECURITY__SESSION_SECRET</code>) and never editable here.
          </p>
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
