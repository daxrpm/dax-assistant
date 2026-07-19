import { useState, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import { getBaseUrl, setBaseUrl, storeToken } from "../api/connection";
import type { AuthStatus } from "../api/types";
import { Button, Field, TextInput, useToast } from "../design/primitives";
import s from "./Login.module.css";

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
  const isSetup = !status.configured;
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endpoint, setEndpoint] = useState(getBaseUrl());
  const [editingEndpoint, setEditingEndpoint] = useState(false);
  const toast = useToast();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (isSetup) {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirm) {
        setError("Passwords do not match.");
        return;
      }
    }

    setBusy(true);
    try {
      const result = isSetup ? await api.setup(password) : await api.login(password);
      if (!result.ok) {
        setError(isSetup ? "Setup failed." : "Incorrect password.");
        return;
      }
      if (result.token) {
        await storeToken(result.token);
      } else {
        // Auth is disabled backend-side; there is nothing to store.
        toast.show("Backend has authentication disabled.");
      }
      onAuthenticated();
    } catch (err) {
      if (err instanceof ApiError && err.isUnreachable) {
        setError(`Cannot reach the backend at ${getBaseUrl()}. Is it running?`);
      } else if (err instanceof ApiError && err.status === 401) {
        setError("Incorrect password.");
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  function saveEndpoint() {
    setBaseUrl(endpoint);
    setEndpoint(getBaseUrl());
    setEditingEndpoint(false);
    toast.show("Backend endpoint updated.");
  }

  return (
    <div className={s.screen}>
      <form className={s.card} onSubmit={submit}>
        <div className={s.brand}>
          <div className={s.title}>{isSetup ? "Welcome to Dax" : "Dax"}</div>
          <div className={s.subtitle}>
            {isSetup ? "Choose a password to secure your assistant." : "Sign in to continue."}
          </div>
        </div>

        <div className={s.form}>
          <Field label="Password" error={error}>
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
            <Field label="Confirm password">
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
            {isSetup ? "Create account" : "Sign in"}
          </Button>
        </div>

        <div className={s.footer}>
          {editingEndpoint ? (
            <>
              <TextInput
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                aria-label="Backend URL"
              />
              <Button size="sm" onClick={saveEndpoint}>
                Save
              </Button>
            </>
          ) : (
            <>
              <span className={s.endpoint} title={endpoint}>
                {endpoint}
              </span>
              <Button size="sm" variant="ghost" onClick={() => setEditingEndpoint(true)}>
                Change
              </Button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
