import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { MemoryEntry, MemoryType } from "../../api/types";
import { BrainIcon, PlusIcon, SearchIcon, TrashIcon } from "../../components/icons";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  IconButton,
  Panel,
  PanelBody,
  PanelHeader,
  Select,
  Spinner,
  TextArea,
  TextInput,
  useToast,
} from "../../design/primitives";
import { cn } from "../../lib/cn";
import p from "../page.module.css";
import s from "./MemoryTab.module.css";
import { useI18n } from "../../i18n/I18n";

const TYPES: MemoryType[] = ["user", "feedback", "project", "reference"];

const TYPE_TONE: Record<MemoryType, "accent" | "success" | "warning" | "neutral"> = {
  user: "accent",
  feedback: "warning",
  project: "success",
  reference: "neutral",
};

interface Draft {
  slug: string | null;
  name: string;
  description: string;
  type: MemoryType;
  body: string;
}

function emptyDraft(): Draft {
  return { slug: null, name: "", description: "", type: "user", body: "" };
}

export function MemoryTab() {
  const { text } = useI18n();
  const toast = useToast();
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEntries(await api.listMemory());
    } catch (err) {
       toast.show(err instanceof Error ? err.message : text("No se pudo cargar la memoria", "Failed to load memory"), "danger");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.body.toLowerCase().includes(q),
    );
  }, [entries, search]);

  const open = async (entry: MemoryEntry) => {
    // The list response may carry a truncated body; fetch the full record.
    try {
      const full = await api.getMemory(entry.slug);
      setDraft({
        slug: full.slug,
        name: full.name,
        description: full.description,
        type: full.type,
        body: full.body,
      });
    } catch {
      setDraft({
        slug: entry.slug,
        name: entry.name,
        description: entry.description,
        type: entry.type,
        body: entry.body,
      });
    }
  };

  const save = async () => {
    if (!draft || !draft.name.trim()) return;
    setSaving(true);
    try {
      if (draft.slug) {
        await api.updateMemory(draft.slug, {
          name: draft.name,
          description: draft.description,
          type: draft.type,
          body: draft.body,
        });
      } else {
        await api.createMemory({
          name: draft.name,
          description: draft.description,
          type: draft.type,
          body: draft.body,
        });
      }
      toast.show(text("Memoria guardada", "Memory saved"), "success");
      setDraft(null);
      await load();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : text("No se pudo guardar", "Save failed"), "danger");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (slug: string) => {
    try {
      await api.deleteMemory(slug);
      toast.show(text("Memoria eliminada", "Memory deleted"), "success");
      if (draft?.slug === slug) setDraft(null);
      await load();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : text("No se pudo eliminar", "Delete failed"), "danger");
    }
  };

  return (
    <Panel>
      <PanelHeader
        title={text("Memoria", "Memory")}
        subtitle={text(`${entries.length} entrada(s)`, `${entries.length} entries`)}
        actions={
          <Button size="sm" variant="primary" onClick={() => setDraft(emptyDraft())}>
            <PlusIcon size={13} />
            {text("Nueva entrada", "New entry")}
          </Button>
        }
      />
      <PanelBody>
        <div className={s.split}>
          <div className={s.listPane}>
            <div className={s.searchWrap}>
              <span className={s.searchIcon}>
                <SearchIcon size={13} />
              </span>
              <TextInput
                className={s.searchInput}
                value={search}
                placeholder={text("Buscar en la memoria", "Search memory")}
                aria-label={text("Buscar en la memoria", "Search memory")}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            {loading ? (
              <Spinner size={16} />
            ) : filtered.length === 0 ? (
              <p className={p.hint}>{search ? text("Sin coincidencias", "No matches") : text("Aún no hay entradas de memoria.", "No memory entries yet.")}</p>
            ) : (
              <div className={s.entryList} aria-label={text("Entradas de memoria", "Memory entries")}>
                {filtered.map((entry) => (
                  <div
                    key={entry.slug}
                    className={cn(
                      s.entry,
                      draft?.slug === entry.slug && s.entrySelected,
                    )}
                  >
                    <button
                      type="button"
                      className={s.entryOpen}
                      aria-pressed={draft?.slug === entry.slug}
                      onClick={() => void open(entry)}
                    >
                      <span className={s.entryHead}>
                        <span className={s.entryName}>{entry.name}</span>
                        <Badge tone={TYPE_TONE[entry.type]}>{entry.type}</Badge>
                      </span>
                      {entry.description && (
                        <span className={s.entryDesc}>{entry.description}</span>
                      )}
                    </button>
                    <span className={s.entryDelete}>
                      <IconButton
                        label={`Delete ${entry.name}`}
                        danger
                        onClick={(e) => {
                          e.stopPropagation();
                          void remove(entry.slug);
                        }}
                      >
                        <TrashIcon size={12} />
                      </IconButton>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className={s.editorPane}>
            {!draft ? (
              <EmptyState
                icon={<BrainIcon size={20} />}
                title={text("Ninguna entrada seleccionada", "No entry selected")}
                body={text("Selecciona una entrada para editarla o crea una nueva. Son markdown y se incorporan al contexto del asistente.", "Pick an entry to edit it, or create a new one. Entries are markdown and are injected into the assistant's context.")}
              />
            ) : (
              <div className={p.rows}>
                <div className={p.row2}>
                   <Field label={text("Título", "Title")}>
                    {(id) => (
                      <TextInput
                        id={id}
                        value={draft.name}
                        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                      />
                    )}
                  </Field>
                   <Field label={text("Tipo", "Type")}>
                    {(id) => (
                      <Select
                        id={id}
                        value={draft.type}
                        onChange={(e) =>
                          setDraft({ ...draft, type: e.target.value as MemoryType })
                        }
                      >
                        {TYPES.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                </div>

                 <Field label={text("Descripción", "Description")} description={text("Una línea, visible en la lista.", "One line, shown in the list.")}>
                  {(id) => (
                    <TextInput
                      id={id}
                      value={draft.description}
                      onChange={(e) =>
                        setDraft({ ...draft, description: e.target.value })
                      }
                    />
                  )}
                </Field>

                 <Field label={text("Contenido", "Body")} description="Markdown.">
                  {(id) => (
                    <TextArea
                      id={id}
                      rows={16}
                      value={draft.body}
                      onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                    />
                  )}
                </Field>

                <div className={p.actionsEnd}>
                  <Button variant="ghost" onClick={() => setDraft(null)}>
                     {text("Cancelar", "Cancel")}
                  </Button>
                  <Button
                    variant="primary"
                    loading={saving}
                    disabled={!draft.name.trim() || saving}
                    onClick={() => void save()}
                  >
                     {text("Guardar", "Save")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </PanelBody>
    </Panel>
  );
}
