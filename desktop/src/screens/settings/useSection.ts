import { useCallback, useEffect, useState } from "react";
import { useToast } from "../../design/primitives";

/**
 * Editable copy of one config section, with dirty tracking and save.
 *
 * Every settings tab has the same shape: take the server's section, let the
 * user edit a local draft, PATCH it, then refresh the whole config so masked
 * secret indicators (`*_configured`, `has_token`, …) come back from the server
 * rather than being inferred locally.
 */
export function useSection<T extends object>(
  section: T,
  save: (patch: Record<string, unknown>) => Promise<unknown>,
  onSaved: () => void,
  successMessage = "Saved",
) {
  const toast = useToast();
  const [draft, setDraft] = useState<T>(section);
  const [saving, setSaving] = useState(false);

  // Re-seed when the server view changes (after a refresh, or a tab switch).
  useEffect(() => {
    setDraft(section);
  }, [section]);

  const set = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }, []);

  const dirty = JSON.stringify(draft) !== JSON.stringify(section);

  const commit = useCallback(
    async (patch?: Record<string, unknown>) => {
      setSaving(true);
      try {
        await save(patch ?? (draft as unknown as Record<string, unknown>));
        toast.show(successMessage, "success");
        onSaved();
      } catch (err) {
        toast.show(err instanceof Error ? err.message : "Save failed", "danger");
      } finally {
        setSaving(false);
      }
    },
    [draft, save, onSaved, toast, successMessage],
  );

  return { draft, set, setDraft, dirty, saving, commit };
}

/**
 * Save-button caption. A plain function, not a hook — it is called inside JSX
 * expressions where hook ordering would be fragile.
 */
export function saveLabel(dirty: boolean, saving: boolean): string {
  if (saving) return "Saving…";
  return dirty ? "Save changes" : "Saved";
}
