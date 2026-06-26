import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { Terminal } from "lucide-react";
import { api } from "../api/client";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  Badge,
  useToast,
} from "../components/ui";

/**
 * Dedicated page to manage the shell-command allowlist — the binaries the
 * assistant may run on this PC. Commands here run without asking; anything else
 * prompts for confirmation in chat (where you can approve & save it here).
 */
export function ShellPage() {
  const toast = useToast();
  const [commands, setCommands] = useState<string[]>([]);
  const [defaults, setDefaults] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .getShellAllow()
      .then((res) => {
        if (!active) return;
        setCommands(res.commands);
        setDefaults(res.default);
      })
      .catch((e) => {
        if (active) toast.show(e instanceof Error ? e.message : "Failed to load", "danger");
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addCommands = (raw: string) => {
    const parts = raw
      .split(/[\s,]+/)
      .map((p) => p.trim())
      .filter(Boolean);
    if (parts.length === 0) return;
    setCommands((prev) => {
      const next = [...prev];
      for (const p of parts) if (!next.includes(p)) next.push(p);
      return next;
    });
    setDirty(true);
    setDraft("");
  };

  const removeCommand = (cmd: string) => {
    setCommands((prev) => prev.filter((c) => c !== cmd));
    setDirty(true);
  };

  const restoreDefaults = () => {
    setCommands(defaults);
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      const res = await api.updateShellAllow(commands);
      setCommands(res.commands);
      setDirty(false);
      toast.show("Allowlist saved", "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto p-6 scroll-slim">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
        <Panel>
          <PanelHeader
            title="Allowed shell commands"
            description="Binaries the assistant may run on this computer. Allowlisted commands run without asking; anything else prompts you in chat, where you can approve & save it here."
            action={<Badge color="accent">{commands.length} allowed</Badge>}
          />
          {loading ? (
            <p className="text-sm text-muted">Loading…</p>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-2 rounded-xl border border-separator bg-background p-3 min-h-[3rem]">
                {commands.length === 0 && (
                  <span className="text-sm text-muted">
                    No commands allowed — the shell tool will refuse everything until
                    you approve one in chat or add it here.
                  </span>
                )}
                {commands.map((cmd) => (
                  <span
                    key={cmd}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-separator bg-surface px-2 py-1 text-sm font-mono"
                  >
                    {cmd}
                    <button
                      type="button"
                      aria-label={`Remove ${cmd}`}
                      onClick={() => removeCommand(cmd)}
                      className="text-muted transition-colors hover:text-danger"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <Field
                label="Add commands"
                description="Bare binary names only (e.g. flatpak). Press Enter, comma or space to add several."
              >
                <TextInput
                  value={draft}
                  placeholder="flatpak, docker, kubectl…"
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === ",") {
                      e.preventDefault();
                      addCommands(draft);
                    }
                  }}
                  onBlur={() => draft.trim() && addCommands(draft)}
                />
              </Field>
              <div className="flex items-center justify-between">
                <Button variant="ghost" onPress={restoreDefaults}>
                  Restore defaults
                </Button>
                <Button variant="primary" onPress={save} isDisabled={saving || !dirty}>
                  {saving ? "Saving…" : "Save"}
                </Button>
              </div>
            </div>
          )}
        </Panel>

        <Panel>
          <PanelHeader
            title="How it works"
            description="The safety model for local command execution"
          />
          <ul className="flex flex-col gap-2 text-sm text-muted">
            <li className="flex gap-2">
              <Terminal size={16} className="mt-0.5 shrink-0 text-accent" />
              Commands always run argv-only (no shell, no pipes or redirection), so
              they can't be chained or injected.
            </li>
            <li className="flex gap-2">
              <Terminal size={16} className="mt-0.5 shrink-0 text-accent" />
              A binary in this list runs immediately. Anything else asks you in chat:
              you can <strong>Approve once</strong> or <strong>Approve &amp; save</strong>
              (which adds it here).
            </li>
            <li className="flex gap-2">
              <Terminal size={16} className="mt-0.5 shrink-0 text-accent" />
              Changes apply instantly — no restart needed.
            </li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}
