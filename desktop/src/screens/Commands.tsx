import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { AlertIcon, PlusIcon, TerminalIcon, XIcon } from "../components/icons";
import {
  Button,
  Field,
  IconButton,
  Panel,
  PanelBody,
  PanelHeader,
  Spinner,
  TextInput,
  useToast,
} from "../design/primitives";
import p from "./page.module.css";

/**
 * Split a free-text entry into command names.
 *
 * Users paste lists in whatever shape they have them — space, comma or newline
 * separated — so accept all three rather than making them reformat.
 */
function splitCommands(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((c) => c.trim())
    .filter(Boolean);
}

/** `dax-system` shell allowlist editor (`GET`/`PUT /api/config/system/shell-allow`). */
export function Commands() {
  const toast = useToast();
  const [commands, setCommands] = useState<string[]>([]);
  const [defaults, setDefaults] = useState<string[]>([]);
  const [saved, setSaved] = useState<string[]>([]);
  const [entry, setEntry] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .shellAllow()
      .then((data) => {
        setCommands(data.commands);
        setSaved(data.commands);
        setDefaults(data.default);
      })
      .catch((err: unknown) =>
        toast.show(err instanceof Error ? err.message : "Failed to load", "danger"),
      )
      .finally(() => setLoading(false));
  }, [toast]);

  const dirty = useMemo(
    () =>
      commands.length !== saved.length ||
      commands.some((c, i) => c !== saved[i]),
    [commands, saved],
  );

  const add = () => {
    const additions = splitCommands(entry);
    if (additions.length === 0) return;
    setCommands((prev) => [...new Set([...prev, ...additions])].sort());
    setEntry("");
  };

  const remove = (cmd: string) =>
    setCommands((prev) => prev.filter((c) => c !== cmd));

  const save = async () => {
    setSaving(true);
    try {
      await api.updateShellAllow(commands);
      setSaved(commands);
      toast.show("Allowlist saved", "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Spinner size={18} />;

  return (
    <div className={p.page}>
      <div className={p.pageHead}>
        <div className={p.pageMark}>
          <TerminalIcon size={19} />
        </div>
        <div>
          <h1 className={p.pageTitle}>Commands</h1>
          <p className={p.pageSubtitle}>
            Shell binaries the assistant may run without asking
          </p>
        </div>
      </div>

      <div className={p.notice}>
        <span className={p.noticeIcon}>
          <AlertIcon size={14} />
        </span>
        <span>
          Commands listed here run immediately when the assistant calls them. Anything
          not listed prompts you in chat, where <strong>Approve &amp; save</strong> adds
          it to this list. Paths stay confined to the configured roots either way.
        </span>
      </div>

      <Panel>
        <PanelHeader
          title="Allowlist"
          subtitle={`${commands.length} command${commands.length !== 1 ? "s" : ""}`}
          actions={
            <div className={p.actions}>
              <Button
                size="sm"
                variant="ghost"
                disabled={saving}
                onClick={() => setCommands([...defaults].sort())}
              >
                Reset to defaults
              </Button>
              <Button
                size="sm"
                variant="primary"
                loading={saving}
                disabled={!dirty || saving}
                onClick={() => void save()}
              >
                {dirty ? "Save changes" : "Saved"}
              </Button>
            </div>
          }
        />
        <PanelBody>
          <div className={p.stack}>
            <Field
              label="Add commands"
              description="Separate with spaces, commas or newlines. Duplicates are ignored."
            >
              {(id) => (
                <div className={p.actions}>
                  <TextInput
                    id={id}
                    className={p.grow}
                    value={entry}
                    placeholder="rg fd jq"
                    onChange={(e) => setEntry(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        add();
                      }
                    }}
                  />
                  <Button variant="secondary" onClick={add} disabled={!entry.trim()}>
                    <PlusIcon size={13} />
                    Add
                  </Button>
                </div>
              )}
            </Field>

            {commands.length === 0 ? (
              <p className={p.hint}>
                Nothing allowlisted — every shell call will ask for confirmation.
              </p>
            ) : (
              <div className={p.tagList}>
                {commands.map((cmd) => (
                  <span key={cmd} className={p.tag}>
                    {cmd}
                    <IconButton label={`Remove ${cmd}`} danger onClick={() => remove(cmd)}>
                      <XIcon size={11} />
                    </IconButton>
                  </span>
                ))}
              </div>
            )}
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Defaults"
          subtitle="Shipped with dax-system, for reference"
        />
        <PanelBody>
          <div className={p.tagList}>
            {defaults.map((cmd) => (
              <span key={cmd} className={`${p.tag} ${p.tagDefault}`}>
                {cmd}
              </span>
            ))}
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
