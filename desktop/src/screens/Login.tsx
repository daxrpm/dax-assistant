import { useState, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import { getBaseUrl, storeToken } from "../api/connection";
import { AppIcon } from "../components/AppIcon";
import type { AuthStatus } from "../api/types";
import { Button, Field, TextInput, useToast } from "../design/primitives";
import s from "./Login.module.css";
import { useI18n } from "../i18n/I18n";

/**
 * Login + first-run setup, mirroring `web/src/pages/Login.tsx`.
 *
 * The desktop-specific part: on success we persist the token returned in the
 * login body (PLAN.md 3.5) rather than trusting cookie replay, and we let the
 * user point the app at a different backend origin.
 */
export function Login({
  status,
  onAuthenticated,
}: {
  status: AuthStatus;
  onAuthenticated: () => void;
}) {
  const { t } = useI18n();
  const isSetup = !status.configured;
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endpoint = getBaseUrl();
  const toast = useToast();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (isSetup) {
      if (password.length < 8) {
        setError(t("login.passwordShort"));
        return;
      }
      if (password !== confirm) {
        setError(t("login.passwordMismatch"));
        return;
      }
    }

    setBusy(true);
    try {
      const result = isSetup ? await api.setup(password) : await api.login(password);
      if (!result.ok) {
        setError(isSetup ? t("login.setupFailed") : t("login.incorrect"));
        return;
      }
      if (result.token) {
        await storeToken(result.token);
      } else {
        // Auth is disabled backend-side; there is nothing to store.
        toast.show(t("login.authDisabled"));
      }
      onAuthenticated();
    } catch (err) {
      if (err instanceof ApiError && err.isUnreachable) {
        setError(t("login.cannotReach", { url: getBaseUrl() }));
      } else if (err instanceof ApiError && err.status === 401) {
        setError(t("login.incorrect"));
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={s.screen}>
      <form className={s.card} onSubmit={submit}>
        <div className={s.brand}>
          <AppIcon size={58} className={s.appIcon} />
          <div className={s.title}>{isSetup ? t("login.welcome") : "Dax"}</div>
          <div className={s.subtitle}>
            {isSetup ? t("login.setupSubtitle") : t("login.signInSubtitle")}
          </div>
        </div>

        <div className={s.form}>
          <Field label={t("login.password")} error={error}>
            {(id) => (
              <TextInput
                id={id}
                type="password"
                autoFocus
                autoComplete={isSetup ? "new-password" : "current-password"}
                value={password}
                invalid={!!error}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>

          {isSetup && (
            <Field label={t("login.confirm")}>
              {(id) => (
                <TextInput
                  id={id}
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              )}
            </Field>
          )}

          <Button type="submit" variant="primary" fullWidth loading={busy}>
            {isSetup ? t("login.create") : t("login.signIn")}
          </Button>
        </div>

        <div className={s.footer}>
          <span className={s.endpoint} title={endpoint}>{endpoint}</span>
          <Button size="sm" variant="ghost" onClick={() => window.dispatchEvent(new Event("dax:open-onboarding"))}>
            {t("login.change")}
          </Button>
        </div>
      </form>
    </div>
  );
}
