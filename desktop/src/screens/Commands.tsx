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
import { useI18n } from "../i18n/I18n";

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
  const { text } = useI18n();
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
        toast.show(err instanceof Error ? err.message : text("No se pudo cargar", "Failed to load"), "danger"),
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
      toast.show(text("Lista de permitidos guardada", "Allowlist saved"), "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : text("No se pudo guardar", "Save failed"), "danger");
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
          <h1 className={p.pageTitle}>{text("Comandos", "Commands")}</h1>
          <p className={p.pageSubtitle}>
            {text("Binarios de shell que el asistente puede ejecutar sin preguntar", "Shell binaries the assistant may run without asking")}
          </p>
        </div>
      </div>

      <div className={p.notice}>
        <span className={p.noticeIcon}>
          <AlertIcon size={14} />
        </span>
        <span>
          {text("Los comandos de esta lista se ejecutan de inmediato. Los demás piden confirmación en el chat; Aprobar y guardar los añade aquí. Las rutas siempre quedan limitadas a las raíces configuradas.", "Commands listed here run immediately when the assistant calls them. Anything not listed prompts you in chat, where Approve & save adds it to this list. Paths stay confined to the configured roots either way.")}
        </span>
      </div>

      <Panel>
        <PanelHeader
          title={text("Lista de permitidos", "Allowlist")}
          subtitle={text(`${commands.length} comando(s)`, `${commands.length} command(s)`)}
          actions={
            <div className={p.actions}>
              <Button
                size="sm"
                variant="ghost"
                disabled={saving}
                onClick={() => setCommands([...defaults].sort())}
              >
                {text("Restablecer valores predeterminados", "Reset to defaults")}
              </Button>
              <Button
                size="sm"
                variant="primary"
                loading={saving}
                disabled={!dirty || saving}
                onClick={() => void save()}
              >
                {dirty ? text("Guardar cambios", "Save changes") : text("Guardado", "Saved")}
              </Button>
            </div>
          }
        />
        <PanelBody>
          <div className={p.stack}>
            <Field
              label={text("Añadir comandos", "Add commands")}
              description={text("Sepáralos con espacios, comas o saltos de línea. Se ignoran los duplicados.", "Separate with spaces, commas or newlines. Duplicates are ignored.")}
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
                    {text("Añadir", "Add")}
                  </Button>
                </div>
              )}
            </Field>

            {commands.length === 0 ? (
              <p className={p.hint}>
                {text("No hay nada permitido: cada llamada de shell pedirá confirmación.", "Nothing allowlisted — every shell call will ask for confirmation.")}
              </p>
            ) : (
              <div className={p.tagList}>
                {commands.map((cmd) => (
                  <span key={cmd} className={p.tag}>
                    {cmd}
                    <IconButton label={text(`Quitar ${cmd}`, `Remove ${cmd}`)} danger onClick={() => remove(cmd)}>
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
          title={text("Valores predeterminados", "Defaults")}
          subtitle={text("Incluidos con dax-system, como referencia", "Shipped with dax-system, for reference")}
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
