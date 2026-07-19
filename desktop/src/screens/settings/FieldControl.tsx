/**
 * Renders one registry field.
 *
 * PLAN 6.0's field rules live here, in one place, so they cannot drift between
 * sections: the description sits **under the label** (never in a tooltip — a
 * tooltip hides exactly the text that makes a setting comprehensible), the
 * config key is shown in mono as secondary metadata, and whether a change
 * applies live or needs a restart is marked inline.
 */

import { Field, Select, Slider, TextArea, TextInput, Toggle } from "../../design/primitives";
import { cn } from "../../lib/cn";
import type { FieldSpec } from "./registry";
import s from "./settings.module.css";
import type { SettingsDraft } from "./useSettingsDraft";
import { useI18n } from "../../i18n/I18n";

const APPLY_KEY = { live: "settings.live", reload: "settings.reloadVoice", restart: "settings.restartRequired" } as const;

const APPLY_CLASS = {
  live: s.markLive,
  reload: s.markReload,
  restart: s.markRestart,
} as const;

function toLines(value: unknown): string {
  return Array.isArray(value) ? value.join("\n") : "";
}

function fromLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function fromIntLines(text: string): number[] {
  return fromLines(text)
    .map(Number)
    .filter((n) => Number.isFinite(n));
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function asNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function FieldLabel({ field, dirty }: { field: FieldSpec; dirty: boolean }) {
  const { t } = useI18n();
  return (
    <span className={s.fieldHead}>
      <span className={cn(field.danger && s.danger)}>{field.label}</span>
      {field.key && <code className={s.fieldKey}>{field.key}</code>}
      {field.apply && (
        <span className={cn(s.mark, APPLY_CLASS[field.apply])}>
          {t(APPLY_KEY[field.apply])}
        </span>
      )}
      {dirty && <span className={cn(s.mark, s.markDirty)}>{t("settings.unsaved")}</span>}
    </span>
  );
}

export function FieldControl({
  field,
  draft,
}: {
  field: FieldSpec;
  draft: SettingsDraft;
}) {
  const { t } = useI18n();
  const dirty = draft.isDirty(field);
  const value = draft.value(field);
  const label = <FieldLabel field={field} dirty={dirty} />;

  // Not reachable through the HTTP API. Shown rather than hidden, with the
  // reason, because "absolutely every config" means the user must at least be
  // able to find it and learn why it is not editable here.
  if (field.control === "readonly") {
    return (
      <Field label={label} description={field.description}>
        {() => (
          <>
            <div className={s.readonlyBox}>{t("settings.readonly")}</div>
            {field.reason && <div className={s.reason}>{field.reason}</div>}
          </>
        )}
      </Field>
    );
  }

  switch (field.control) {
    case "toggle":
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <Toggle
              id={id}
              checked={Boolean(value)}
              onChange={(next) => draft.setValue(field, next)}
            />
          )}
        </Field>
      );

    case "select":
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <Select
              id={id}
              value={asString(value)}
              onChange={(e) => draft.setValue(field, e.target.value)}
            >
              {(field.options ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
      );

    case "slider":
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <Slider
              id={id}
              value={asNumber(value)}
              min={field.min}
              max={field.max}
              step={field.step}
              onChange={(next) => draft.setValue(field, next)}
            />
          )}
        </Field>
      );

    case "number":
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <div className={s.numberUnit}>
              <TextInput
                id={id}
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                value={asNumber(value)}
                onChange={(e) => draft.setValue(field, Number(e.target.value))}
              />
              {field.unit && <span className={s.unit}>{field.unit}</span>}
            </div>
          )}
        </Field>
      );

    case "textarea":
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <TextArea
              id={id}
              rows={field.rows ?? 4}
              value={asString(value)}
              onChange={(e) => draft.setValue(field, e.target.value)}
            />
          )}
        </Field>
      );

    case "lines":
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <TextArea
              id={id}
              rows={field.rows ?? 4}
              value={toLines(value)}
              onChange={(e) => draft.setValue(field, fromLines(e.target.value))}
            />
          )}
        </Field>
      );

    case "lines-int":
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <TextArea
              id={id}
              rows={field.rows ?? 4}
              value={toLines(value)}
              onChange={(e) => draft.setValue(field, fromIntLines(e.target.value))}
            />
          )}
        </Field>
      );

    // The backend masks secrets on GET and treats an echoed mask as
    // "unchanged". We never receive the value, so the box starts empty and an
    // empty box is simply omitted from the PATCH — same contract, no defeat.
    case "secret":
      return (
        <Field
          label={label}
          description={
            draft.configured(field)
              ? `${t("settings.keyStored")} ${field.description ?? ""}`.trim()
              : field.description
          }
        >
          {(id) => (
            <TextInput
              id={id}
              type="password"
              autoComplete="off"
              placeholder={draft.configured(field) ? "••••••••" : t("settings.notConfigured")}
              value={asString(value)}
              onChange={(e) => draft.setValue(field, e.target.value)}
            />
          )}
        </Field>
      );

    default:
      return (
        <Field label={label} description={field.description}>
          {(id) => (
            <TextInput
              id={id}
              value={asString(value)}
              onChange={(e) => draft.setValue(field, e.target.value)}
            />
          )}
        </Field>
      );
  }
}
