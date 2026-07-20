/**
 * One draft store for the whole Settings surface.
 *
 * Every editable field in `registry.json` names a PATCH route (`api`) and a
 * path inside that route's body (`path`). This hook keeps a single map of
 * pending edits keyed by `route:path`, so dirty state and save can be computed
 * per *group* — PLAN 6.0 requires explicit save per group, never auto-save,
 * because auto-saving a field like `web.host` is hostile.
 */

import { useCallback, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { FullConfig } from "../../api/types";
import { useToast } from "../../design/primitives";
import { draftKey, type ApiSection, type FieldSpec, type GroupSpec } from "./registry";
import { useI18n } from "../../i18n/I18n";

type Saver = (body: Record<string, unknown>) => Promise<unknown>;
type DirtyReader = (field: FieldSpec) => boolean;
type ValueReader = (field: FieldSpec) => unknown;

const SAVERS: Record<ApiSection, Saver> = {
  general: api.updateGeneral,
  voice: api.updateVoice,
  llm: api.updateLLM,
  web: api.updateWeb,
  whatsapp: api.updateWhatsApp,
  telegram: api.updateTelegram,
  security: api.updateSecurity,
  tools: api.updateTools,
  nodes: api.updateNodes,
};

function readPath(root: unknown, path: string): unknown {
  let cursor: unknown = root;
  for (const part of path.split(".")) {
    if (cursor === null || typeof cursor !== "object") return undefined;
    cursor = (cursor as Record<string, unknown>)[part];
  }
  return cursor;
}

function writePath(root: Record<string, unknown>, path: string, value: unknown): void {
  const parts = path.split(".");
  const last = parts.pop();
  if (!last) return;
  let cursor = root;
  for (const part of parts) {
    const next = cursor[part];
    if (next === undefined || next === null || typeof next !== "object") {
      cursor[part] = {};
    }
    cursor = cursor[part] as Record<string, unknown>;
  }
  cursor[last] = value;
}

export function buildGroupBodies(
  group: GroupSpec,
  isDirty: DirtyReader,
  value: ValueReader,
): Map<ApiSection, Record<string, unknown>> {
  const bodies = new Map<ApiSection, Record<string, unknown>>();
  for (const field of group.fields) {
    if (!field.api || !field.path || !isDirty(field)) continue;
    const body = bodies.get(field.api) ?? {};
    writePath(body, field.path, value(field));
    bodies.set(field.api, body);
  }
  return bodies;
}

function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

export interface SettingsDraft {
  value: (field: FieldSpec) => unknown;
  setValue: (field: FieldSpec, next: unknown) => void;
  /** True when a secret is already stored server-side (`*_configured`). */
  configured: (field: FieldSpec) => boolean;
  isDirty: (field: FieldSpec) => boolean;
  groupDirty: (group: GroupSpec) => boolean;
  saveGroup: (group: GroupSpec) => Promise<void>;
  resetGroup: (group: GroupSpec) => void;
  savingGroup: string | null;
}

export function useSettingsDraft(
  config: FullConfig,
  onSaved: () => void,
): SettingsDraft {
  const toast = useToast();
  const { text } = useI18n();
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const [savingGroup, setSavingGroup] = useState<string | null>(null);

  const serverValue = useCallback(
    (field: FieldSpec): unknown => {
      // Secrets are never returned by GET /api/config; the field always starts
      // empty and an empty value means "leave the stored secret alone".
      if (field.control === "secret") return "";
      if (!field.api || !field.path) return undefined;
      return readPath(readPath(config, field.api), field.path);
    },
    [config],
  );

  const value = useCallback(
    (field: FieldSpec): unknown => {
      const key = draftKey(field);
      return key in edits ? edits[key] : serverValue(field);
    },
    [edits, serverValue],
  );

  const setValue = useCallback((field: FieldSpec, next: unknown) => {
    const key = draftKey(field);
    setEdits((prev) => ({ ...prev, [key]: next }));
  }, []);

  const configured = useCallback(
    (field: FieldSpec): boolean => {
      if (!field.api || !field.configured) return false;
      return Boolean(readPath(readPath(config, field.api), field.configured));
    },
    [config],
  );

  const isDirty = useCallback(
    (field: FieldSpec): boolean => {
      const key = draftKey(field);
      if (!(key in edits)) return false;
      const next = edits[key];
      // An untouched secret box is empty, which is the mask contract's
      // "unchanged" — not a pending edit.
      if (field.control === "secret") {
        return typeof next === "string" && next.trim() !== "";
      }
      return !sameValue(next, serverValue(field));
    },
    [edits, serverValue],
  );

  const groupDirty = useCallback(
    (group: GroupSpec) => group.fields.some(isDirty),
    [isDirty],
  );

  const resetGroup = useCallback((group: GroupSpec) => {
    const keys = new Set(group.fields.map(draftKey));
    setEdits((prev) =>
      Object.fromEntries(Object.entries(prev).filter(([k]) => !keys.has(k))),
    );
  }, []);

  const saveGroup = useCallback(
    async (group: GroupSpec) => {
      const bodies = buildGroupBodies(group, isDirty, value);
      if (bodies.size === 0) return;

      setSavingGroup(group.id);
      try {
        for (const [section, body] of bodies) {
          await SAVERS[section](body);
        }
        toast.show(text("Guardado", "Saved"), "success");
        resetGroup(group);
        onSaved();
      } catch (err) {
        toast.show(
          err instanceof Error ? err.message : text("No se pudo guardar", "Could not save"),
          "danger",
        );
      } finally {
        setSavingGroup(null);
      }
    },
    [isDirty, value, toast, resetGroup, onSaved, text],
  );

  return useMemo(
    () => ({
      value,
      setValue,
      configured,
      isDirty,
      groupDirty,
      saveGroup,
      resetGroup,
      savingGroup,
    }),
    [
      value,
      setValue,
      configured,
      isDirty,
      groupDirty,
      saveGroup,
      resetGroup,
      savingGroup,
    ],
  );
}
