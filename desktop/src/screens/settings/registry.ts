/**
 * Typed view over `registry.json` — PLAN.md 6.0.
 *
 * The registry is JSON rather than TSX on purpose. The coverage gate
 * (`tests/unit/test_settings_coverage.py`) walks `DaxConfig.model_fields`
 * recursively and asserts every leaf key appears here; it can read JSON
 * directly, whereas parsing JSX for field keys would be guesswork that rots.
 *
 * Consequence for anyone adding a setting: add it to the JSON, not to a
 * component. The renderer is generic and the gate is the contract.
 */

import raw from "./registry.json";
import type { Locale } from "../../i18n/I18n";
import { localizeRegistry } from "./registry.en";

/** PATCH routes under `/api/config/*` that a group can save to. */
export type ApiSection =
  | "general"
  | "voice"
  | "llm"
  | "web"
  | "whatsapp"
  | "telegram"
  | "security"
  | "tools"
  | "nodes";

export type ControlKind =
  | "text"
  | "textarea"
  | "number"
  | "toggle"
  | "select"
  | "slider"
  | "secret"
  | "lines"
  | "lines-int"
  | "readonly"
  | "custom";

/**
 * When a change takes effect. Saying so at the field is what prevents the
 * "I changed it and nothing happened" failure (PLAN 6.0).
 */
export type ApplyMode = "live" | "reload" | "restart";

/** Groups whose body is a bespoke component rather than generated fields. */
export type CustomGroup =
  | "voice-status"
  | "voice-enrollment"
  | "voice-gallery"
  | "mcp-servers"
  | "capability-nodes"
  | "shell-allow"
  | "system-prompt"
  | "memory-files"
  | "change-password"
  | "desktop";

export interface FieldOption {
  value: string;
  label: string;
}

export interface FieldSpec {
  /** Dotted `DaxConfig` leaf key. Present on every field the gate counts. */
  key?: string;
  /** PATCH route this field saves to. Absent means it is not editable here. */
  api?: ApiSection;
  /** Path inside the section body, dotted for nesting (`policy.allow`). */
  path?: string;
  /** Boolean field in the GET body telling us a secret is already stored. */
  configured?: string;
  label: string;
  description?: string;
  control: ControlKind;
  options?: FieldOption[];
  min?: number;
  max?: number;
  step?: number;
  rows?: number;
  unit?: string;
  /** Hidden behind the group's "Avanzado" disclosure. Correct by default. */
  advanced?: boolean;
  /** Renders a warning tone — this one widens the attack surface. */
  danger?: boolean;
  apply?: ApplyMode;
  /** Why a `readonly` field cannot be edited from here. Required for those. */
  reason?: string;
}

export interface GroupSpec {
  id: string;
  title: string;
  description?: string;
  api?: ApiSection;
  custom?: CustomGroup;
  /** Provider blocks collapse by default: only the active one usually matters. */
  collapsible?: boolean;
  fields: FieldSpec[];
}

export interface SectionSpec {
  id: string;
  title: string;
  description: string;
  groups: GroupSpec[];
}

export const SECTIONS = (raw as { sections: unknown }).sections as SectionSpec[];

export function sectionsForLocale(locale: Locale): SectionSpec[] {
  return locale === "en" ? localizeRegistry(SECTIONS) : SECTIONS;
}

/* ---------------- lookup helpers ---------------- */

/** Stable identity for a field's draft slot: the route plus the body path. */
export function draftKey(field: FieldSpec): string {
  return `${field.api ?? "-"}:${field.path ?? field.key ?? field.label}`;
}

export interface FieldHit {
  section: SectionSpec;
  group: GroupSpec;
  field: FieldSpec;
}

export interface GroupHit {
  section: SectionSpec;
  group: GroupSpec;
  fields: FieldSpec[];
}

export function allFields(sections: SectionSpec[] = SECTIONS): FieldHit[] {
  const out: FieldHit[] = [];
  for (const section of sections) {
    for (const group of section.groups) {
      for (const field of group.fields) {
        out.push({ section, group, field });
      }
    }
  }
  return out;
}

/**
 * Search across label, description AND config key — PLAN 6.0 makes this the
 * primary interaction, so `session_ttl_minutes` must find the field even when
 * the user only remembers the technical name.
 */
export function searchFields(query: string, sections: SectionSpec[] = SECTIONS): FieldHit[] {
  const q = normalize(query);
  if (!q) return [];
  const terms = q.split(/\s+/).filter(Boolean);
  return allFields(sections).filter(({ section, group, field }) => {
    const haystack = normalize(
      [
        field.label,
        field.description ?? "",
        field.key ?? "",
        field.path ?? "",
        group.title,
        section.title,
      ].join(" "),
    );
    return terms.every((term) => haystack.includes(term));
  });
}

/** Groups for the search renderer, with only their matching generated fields. */
export function searchGroups(query: string, sections: SectionSpec[] = SECTIONS): GroupHit[] {
  const fieldHits = searchFields(query, sections);
  const grouped = new Map<string, GroupHit>();
  for (const hit of fieldHits) {
    const id = `${hit.section.id}:${hit.group.id}`;
    const existing = grouped.get(id);
    if (existing) existing.fields.push(hit.field);
    else grouped.set(id, { section: hit.section, group: hit.group, fields: [hit.field] });
  }

  const terms = normalize(query).split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  for (const section of sections) {
    for (const group of section.groups) {
      if (!group.custom || group.fields.length > 0) continue;
      const haystack = normalize(
        [section.title, section.description, group.title, group.description ?? "", group.custom].join(" "),
      );
      if (terms.every((term) => haystack.includes(term))) {
        grouped.set(`${section.id}:${group.id}`, { section, group, fields: [] });
      }
    }
  }
  return [...grouped.values()];
}

/** Accent- and case-insensitive: the UI is Spanish and nobody types tildes. */
function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}
