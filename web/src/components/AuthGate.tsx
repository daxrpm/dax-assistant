import { useEffect, useState, type ReactNode } from "react";
import { api, type AuthStatus } from "../api/client";
import { LoginPage } from "../pages/Login";

/**
 * Gates the app behind authentication. While auth is enabled and the user
 * isn't logged in, it shows the login screen; otherwise it renders the app.
 * Passes `authEnabled` down so the shell can show/hide the logout control.
 */
export function AuthGate({
  children,
}: {
  children: (authEnabled: boolean) => ReactNode;
}) {
  const [status, setStatus] = useState<AuthStatus | null>(null);

  const refresh = () => api.authStatus().then(setStatus).catch(() => setStatus(null));

  useEffect(() => {
    refresh();
  }, []);

  if (status === null) {
    return (
      <div className="flex h-full items-center justify-center bg-background text-muted">
        Loading…
      </div>
    );
  }

  const needsLogin = status.auth_enabled && !status.authenticated;
  if (needsLogin) {
    return <LoginPage onLoggedIn={refresh} configured={status.configured} />;
  }

  return <>{children(status.auth_enabled)}</>;
}
