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
      toast.show(err instanceof Error ? err.message : "Failed to load memory", "danger");
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
      toast.show("Memory saved", "success");
      setDraft(null);
      await load();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (slug: string) => {
    try {
      await api.deleteMemory(slug);
      toast.show("Memory deleted", "success");
      if (draft?.slug === slug) setDraft(null);
      await load();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Delete failed", "danger");
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Memory"
        subtitle={`${entries.length} entr${entries.length === 1 ? "y" : "ies"}`}
        actions={
          <Button size="sm" variant="primary" onClick={() => setDraft(emptyDraft())}>
            <PlusIcon size={13} />
            New entry
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
                placeholder="Search memory"
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            {loading ? (
              <Spinner size={16} />
            ) : filtered.length === 0 ? (
              <p className={p.hint}>{search ? "No matches" : "No memory entries yet."}</p>
            ) : (
              <div className={s.entryList}>
                {filtered.map((entry) => (
                  <div
                    key={entry.slug}
                    role="button"
                    tabIndex={0}
                    onClick={() => void open(entry)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void open(entry);
                    }}
                    className={cn(
                      s.entry,
                      draft?.slug === entry.slug && s.entrySelected,
                    )}
                  >
                    <div className={s.entryHead}>
                      <span className={s.entryName}>{entry.name}</span>
                      <Badge tone={TYPE_TONE[entry.type]}>{entry.type}</Badge>
                    </div>
                    {entry.description && (
                      <p className={s.entryDesc}>{entry.description}</p>
                    )}
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
                title="No entry selected"
                body="Pick an entry to edit it, or create a new one. Entries are markdown and are injected into the assistant's context."
              />
            ) : (
              <div className={p.rows}>
                <div className={p.row2}>
                  <Field label="Title">
                    {(id) => (
                      <TextInput
                        id={id}
                        value={draft.name}
                        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                      />
                    )}
                  </Field>
                  <Field label="Type">
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

                <Field label="Description" description="One line, shown in the list.">
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

                <Field label="Body" description="Markdown.">
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
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    loading={saving}
                    disabled={!draft.name.trim() || saving}
                    onClick={() => void save()}
                  >
                    Save
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
