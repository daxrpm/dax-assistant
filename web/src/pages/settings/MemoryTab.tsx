import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { Brain, Pencil, Trash2, ChevronDown, ChevronRight, AlertCircle } from "lucide-react";
import { api, type MemoryEntry } from "../../api/client";
import type { FullConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  TextArea,
  Badge,
  Modal,
  useToast,
} from "../../components/ui";
import { cn } from "../../lib/cn";

const TYPE_COLOR: Record<string, "accent" | "success" | "warning" | "danger" | "default"> = {
  user: "accent",
  feedback: "success",
  project: "warning",
  reference: "default",
};

function MemoryCard({
  entry,
  onEdit,
  onDelete,
}: {
  entry: MemoryEntry;
  onEdit: (e: MemoryEntry) => void;
  onDelete: (slug: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="group rounded-xl border border-separator bg-background transition-colors hover:border-accent/40">
      <div
        className="flex cursor-pointer items-start gap-3 p-3"
        onClick={() => setExpanded((v) => !v)}
      >
        <button
          type="button"
          className="mt-0.5 shrink-0 text-muted"
          onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{entry.name}</span>
            <Badge color={TYPE_COLOR[entry.type] ?? "default"}>{entry.type}</Badge>
          </div>
          {entry.description && (
            <p className="mt-0.5 text-xs text-muted line-clamp-1">{entry.description}</p>
          )}
        </div>
        <div className="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onEdit(entry); }}
            className="rounded-lg p-1.5 text-muted hover:bg-surface-secondary hover:text-foreground"
          >
            <Pencil size={14} />
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDelete(entry.slug); }}
            className="rounded-lg p-1.5 text-muted hover:bg-danger-soft hover:text-danger-soft-foreground"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      {expanded && (
        <div className="border-t border-separator px-3 pb-3 pt-2">
          <pre className="whitespace-pre-wrap font-mono text-xs text-muted">{entry.body}</pre>
        </div>
      )}
    </div>
  );
}

export function MemoryTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<MemoryEntry | null>(null);
  const [editBody, setEditBody] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [memoryPath, setMemoryPath] = useState(config.general.memory_path ?? "");
  const [pathSaving, setPathSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.listMemory()
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (config.general.memory_path) load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.general.memory_path]);

  const savePath = async () => {
    setPathSaving(true);
    try {
      await api.updateGeneral({ memory_path: memoryPath });
      toast.show("Memory path saved", "success");
      onSaved();
      load();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setPathSaving(false);
    }
  };

  const openEdit = (entry: MemoryEntry) => {
    setEditing(entry);
    setEditBody(entry.body);
    setEditDesc(entry.description);
  };

  const confirmEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await api.updateMemory(editing.slug, { body: editBody, description: editDesc });
      toast.show("Memory updated", "success");
      setEditing(null);
      load();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Update failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async (slug: string) => {
    try {
      await api.deleteMemory(slug);
      setEntries((prev) => prev.filter((e) => e.slug !== slug));
      toast.show("Memory deleted", "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Delete failed", "danger");
    }
  };

  const configured = Boolean(config.general.memory_path);

  return (
    <div className="flex flex-col gap-5">
      <Panel>
        <PanelHeader
          title="Memory path"
          description="Directory where Claude Code stores memory files for this project"
        />
        <div className="flex flex-col gap-3">
          <Field
            label="Path"
            description="Absolute path to the memory/ directory (e.g. ~/.claude/projects/…/memory)"
          >
            <TextInput
              value={memoryPath}
              onChange={(e) => setMemoryPath(e.target.value)}
              placeholder="/home/user/.claude/projects/.../memory"
            />
          </Field>
          <div className="flex justify-end">
            <Button variant="primary" onPress={savePath} isDisabled={pathSaving}>
              {pathSaving ? "Saving…" : "Save path"}
            </Button>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHeader
          title="Memories"
          description={`What Dax remembers about you — ${entries.length} entries`}
          action={
            configured ? (
              <Button variant="ghost" size="sm" onPress={load} isDisabled={loading}>
                {loading ? "Loading…" : "Refresh"}
              </Button>
            ) : undefined
          }
        />
        {!configured ? (
          <div className="flex items-center gap-2 rounded-xl border border-warning/40 bg-warning-soft px-3 py-2.5 text-sm text-warning-soft-foreground">
            <AlertCircle size={16} />
            Set the memory path above to view and manage memories.
          </div>
        ) : loading ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-muted">
            <Brain size={32} className="opacity-30" />
            <p className="text-sm">No memories saved yet</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {entries.map((e) => (
              <MemoryCard
                key={e.slug}
                entry={e}
                onEdit={openEdit}
                onDelete={confirmDelete}
              />
            ))}
          </div>
        )}
      </Panel>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={`Edit: ${editing?.name}`}
        footer={
          <>
            <Button variant="ghost" onPress={() => setEditing(null)}>Cancel</Button>
            <Button variant="primary" onPress={confirmEdit} isDisabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Field label="Description">
            <TextInput
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
            />
          </Field>
          <Field label="Content">
            <TextArea
              rows={8}
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
              className={cn("font-mono text-xs")}
            />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
