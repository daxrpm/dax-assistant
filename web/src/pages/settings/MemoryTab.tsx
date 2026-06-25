import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Chip,
  Input,
  ListBox,
  Modal,
  Select,
  TextArea,
} from "@heroui/react";
import {
  Brain,
  Check,
  FileText,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { api, type MemoryEntry } from "../../api/client";
import type { FullConfig } from "../../types/config";
import { useToast } from "../../components/ui";

const MEMORY_TYPES = [
  { id: "user", label: "User" },
  { id: "feedback", label: "Feedback" },
  { id: "project", label: "Project" },
  { id: "reference", label: "Reference" },
] as const;

const TYPE_COLOR: Record<MemoryEntry["type"], "accent" | "success" | "warning" | "default"> = {
  user: "accent",
  feedback: "success",
  project: "warning",
  reference: "default",
};

type MemoryDraft = {
  name: string;
  description: string;
  type: MemoryEntry["type"];
  body: string;
};

const EMPTY_DRAFT: MemoryDraft = {
  name: "",
  description: "",
  type: "user",
  body: "",
};

function TypeSelect({
  value,
  onChange,
}: {
  value: MemoryEntry["type"];
  onChange: (value: MemoryEntry["type"]) => void;
}) {
  return (
    <Select selectedKey={value} onSelectionChange={(key) => onChange(String(key) as MemoryEntry["type"])}>
      <Select.Trigger>
        <Select.Value />
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover>
        <ListBox>
          {MEMORY_TYPES.map((item) => (
            <ListBox.Item id={item.id} key={item.id} textValue={item.label}>
              <div className="flex w-full items-center justify-between gap-3">
                <span>{item.label}</span>
                <ListBox.ItemIndicator>
                  <Check size={14} />
                </ListBox.ItemIndicator>
              </div>
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select>
  );
}

function MemoryEditor({
  open,
  title,
  draft,
  saving,
  onChange,
  onClose,
  onSave,
}: {
  open: boolean;
  title: string;
  draft: MemoryDraft;
  saving: boolean;
  onChange: (draft: MemoryDraft) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <Modal isOpen={open} onOpenChange={(next) => !next && onClose()}>
      <Modal.Backdrop>
        <Modal.Container size="lg" scroll="inside">
          <Modal.Dialog>
            <Modal.Header>
              <Modal.Heading>{title}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <div className="grid gap-4">
                <Input
                  aria-label="Memory title"
                  placeholder="Title"
                  value={draft.name}
                  onChange={(event) => onChange({ ...draft, name: event.target.value })}
                  fullWidth
                />
                <Input
                  aria-label="Memory description"
                  placeholder="Short description"
                  value={draft.description}
                  onChange={(event) => onChange({ ...draft, description: event.target.value })}
                  fullWidth
                />
                <TypeSelect
                  value={draft.type}
                  onChange={(type) => onChange({ ...draft, type })}
                />
                <TextArea
                  aria-label="Memory content"
                  placeholder="What should Dax remember?"
                  rows={10}
                  value={draft.body}
                  onChange={(event) => onChange({ ...draft, body: event.target.value })}
                  fullWidth
                  className="font-mono text-sm"
                />
              </div>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="tertiary" onPress={onClose}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onPress={onSave}
                isDisabled={saving || !draft.name.trim()}
              >
                {saving ? <Loader2 size={16} className="animate-spin" /> : null}
                Save
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
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
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState("");
  const [activeType, setActiveType] = useState<"all" | MemoryEntry["type"]>("all");
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<"create" | "edit" | null>(null);
  const [draft, setDraft] = useState<MemoryDraft>(EMPTY_DRAFT);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.listMemory();
      setEntries(data);
      setSelectedSlug((current) => {
        if (current && data.some((entry) => entry.slug === current)) return current;
        return data[0]?.slug ?? null;
      });
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Failed to load memory", "danger");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    if (!config.general.memory_path) onSaved();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return entries.filter((entry) => {
      const matchesType = activeType === "all" || entry.type === activeType;
      const matchesQuery =
        !q ||
        entry.name.toLowerCase().includes(q) ||
        entry.description.toLowerCase().includes(q) ||
        entry.body.toLowerCase().includes(q);
      return matchesType && matchesQuery;
    });
  }, [activeType, entries, query]);

  const selected = entries.find((entry) => entry.slug === selectedSlug) ?? filtered[0] ?? null;

  const openCreate = () => {
    setDraft(EMPTY_DRAFT);
    setEditorMode("create");
  };

  const openEdit = (entry: MemoryEntry) => {
    setDraft({
      name: entry.name,
      description: entry.description,
      type: entry.type,
      body: entry.body,
    });
    setSelectedSlug(entry.slug);
    setEditorMode("edit");
  };

  const closeEditor = () => {
    setEditorMode(null);
    setDraft(EMPTY_DRAFT);
  };

  const saveDraft = async () => {
    setSaving(true);
    try {
      if (editorMode === "create") {
        const created = await api.createMemory(draft);
        toast.show("Memory added", "success");
        await load();
        setSelectedSlug(created.slug);
      } else if (editorMode === "edit" && selected) {
        await api.updateMemory(selected.slug, draft);
        toast.show("Memory updated", "success");
        await load();
      }
      closeEditor();
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  const deleteMemory = async (entry: MemoryEntry) => {
    setSaving(true);
    try {
      await api.deleteMemory(entry.slug);
      toast.show("Memory deleted", "success");
      await load();
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Delete failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid min-h-[620px] grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <Card>
        <Card.Header className="flex items-start justify-between gap-3">
          <div>
            <Card.Title className="flex items-center gap-2">
              <Brain size={18} />
              Memory
            </Card.Title>
            <Card.Description>{entries.length} saved entries</Card.Description>
          </div>
          <Button isIconOnly size="sm" variant="primary" onPress={openCreate} aria-label="Add memory">
            <Plus size={16} />
          </Button>
        </Card.Header>
        <Card.Content className="grid gap-3">
          <Input
            aria-label="Search memory"
            placeholder="Search memory"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            fullWidth
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant={activeType === "all" ? "primary" : "ghost"} onPress={() => setActiveType("all")}>
              All
            </Button>
            {MEMORY_TYPES.map((type) => (
              <Button
                key={type.id}
                size="sm"
                variant={activeType === type.id ? "primary" : "ghost"}
                onPress={() => setActiveType(type.id)}
              >
                {type.label}
              </Button>
            ))}
          </div>
          <div className="flex max-h-[420px] flex-col gap-2 overflow-y-auto pr-1 scroll-slim">
            {loading ? (
              <div className="flex items-center gap-2 py-6 text-sm text-muted">
                <Loader2 size={16} className="animate-spin" />
                Loading memory
              </div>
            ) : filtered.length === 0 ? (
              <div className="rounded-xl border border-dashed border-separator p-5 text-center text-sm text-muted">
                No memories match this view.
              </div>
            ) : (
              filtered.map((entry) => (
                <button
                  key={entry.slug}
                  type="button"
                  onClick={() => setSelectedSlug(entry.slug)}
                  className={`rounded-xl border p-3 text-left transition-colors ${
                    selected?.slug === entry.slug
                      ? "border-accent bg-accent-soft"
                      : "border-separator bg-background hover:border-accent/50"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{entry.name}</span>
                    <Chip size="sm" color={TYPE_COLOR[entry.type]}>{entry.type}</Chip>
                  </div>
                  <p className="line-clamp-2 text-xs text-muted">
                    {entry.description || entry.body || "No details yet"}
                  </p>
                </button>
              ))
            )}
          </div>
        </Card.Content>
        <Card.Footer className="justify-between">
          <span className="truncate text-xs text-muted">{config.general.memory_path || "~/.dax/memory"}</span>
          <Button isIconOnly size="sm" variant="ghost" onPress={load} aria-label="Refresh memory">
            <RefreshCw size={15} />
          </Button>
        </Card.Footer>
      </Card>

      <Card>
        {selected ? (
          <>
            <Card.Header className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Chip color={TYPE_COLOR[selected.type]}>{selected.type}</Chip>
                  <span className="font-mono text-xs text-muted">{selected.filename}</span>
                </div>
                <Card.Title className="truncate">{selected.name}</Card.Title>
                {selected.description ? (
                  <Card.Description>{selected.description}</Card.Description>
                ) : null}
              </div>
              <div className="flex shrink-0 gap-1">
                <Button isIconOnly variant="ghost" onPress={() => openEdit(selected)} aria-label="Edit memory">
                  <Pencil size={16} />
                </Button>
                <Button
                  isIconOnly
                  variant="ghost"
                  onPress={() => deleteMemory(selected)}
                  isDisabled={saving}
                  aria-label="Delete memory"
                >
                  <Trash2 size={16} className="text-danger" />
                </Button>
              </div>
            </Card.Header>
            <Card.Content>
              <pre className="min-h-[420px] whitespace-pre-wrap rounded-xl bg-background p-4 font-mono text-sm leading-6 text-foreground">
                {selected.body || "Empty memory"}
              </pre>
            </Card.Content>
          </>
        ) : (
          <Card.Content className="flex min-h-[560px] flex-col items-center justify-center gap-3 text-center text-muted">
            <FileText size={42} className="opacity-40" />
            <div>
              <p className="text-sm font-medium text-foreground">No memory selected</p>
              <p className="text-sm">Create the first memory entry to start.</p>
            </div>
            <Button variant="primary" onPress={openCreate}>
              <Plus size={16} />
              Add memory
            </Button>
          </Card.Content>
        )}
      </Card>

      <MemoryEditor
        open={editorMode !== null}
        title={editorMode === "create" ? "Add memory" : "Edit memory"}
        draft={draft}
        saving={saving}
        onChange={setDraft}
        onClose={closeEditor}
        onSave={saveDraft}
      />
    </div>
  );
}
