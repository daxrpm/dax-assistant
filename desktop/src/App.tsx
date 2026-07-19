import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "./api/client";
import { clearToken, loadToken } from "./api/connection";
import type { AuthStatus } from "./api/types";
import { AppShell } from "./components/AppShell";
import { Spinner, ToastProvider } from "./design/primitives";
import { useHashRoute } from "./lib/useHashRoute";
import { useTheme } from "./lib/useTheme";
import { Chat } from "./screens/Chat";
import { Commands } from "./screens/Commands";
import { Dashboard } from "./screens/Dashboard";
import { Login } from "./screens/Login";
import { Logs } from "./screens/Logs";
import { Marketplace } from "./screens/Marketplace";
import { Mcp } from "./screens/Mcp";
import { Settings } from "./screens/Settings";
import s from "./App.module.css";

type Phase = "booting" | "unauthenticated" | "authenticated" | "unreachable";

function AppInner() {
  const [phase, setPhase] = useState<Phase>("booting");
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [route, navigate] = useHashRoute("/chat");
  const { mode, setMode } = useTheme();

  const checkAuth = useCallback(async () => {
    try {
      // The token must be in memory before any request so `authStatus` is
      // evaluated with the bearer header attached.
      await loadToken();
      const status = await api.authStatus();
      setAuthStatus(status);
      setPhase(
        !status.auth_enabled || status.authenticated
          ? "authenticated"
          : "unauthenticated",
      );
      setBootError(null);
    } catch (err) {
      if (err instanceof ApiError && err.isUnreachable) {
        setBootError(err.message);
        setPhase("unreachable");
        return;
      }
      setBootError(err instanceof Error ? err.message : String(err));
      setPhase("unauthenticated");
    }
  }, []);

  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Signing out locally matters more than the server round-trip.
    }
    await clearToken();
    setPhase("unauthenticated");
    void checkAuth();
  }, [checkAuth]);

  if (phase === "booting") {
    return (
      <div className={s.center}>
        <Spinner size={20} />
      </div>
    );
  }

  if (phase === "unreachable") {
    return (
      <div className={s.center}>
        <div className={s.message}>
          <div className={s.messageTitle}>Backend unreachable</div>
          <div className={s.messageBody}>{bootError}</div>
          <div className={s.messageHint}>
            Start it with <code>uv run dax</code> or the systemd user unit, then retry.
          </div>
          <button type="button" className={s.retry} onClick={() => void checkAuth()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (phase === "unauthenticated" && authStatus) {
    return <Login status={authStatus} onAuthenticated={() => void checkAuth()} />;
  }

  // Screens that lay out their own full-height chrome opt out of the shell's
  // padded scroll container.
  const BARE_ROUTES = ["/chat", "/logs", "/settings"];

  const screen =
    route === "/chat" ? (
      <Chat />
    ) : route === "/mcp" ? (
      <Mcp />
    ) : route === "/marketplace" ? (
      <Marketplace />
    ) : route === "/commands" ? (
      <Commands />
    ) : route === "/logs" ? (
      <Logs />
    ) : route === "/settings" ? (
      <Settings />
    ) : (
      <Dashboard onUnauthorized={() => setPhase("unauthenticated")} />
    );

  return (
    <AppShell
      route={route}
      onNavigate={navigate}
      themeMode={mode}
      onCycleTheme={setMode}
      onLogout={() => void logout()}
      bare={BARE_ROUTES.includes(route)}
    >
      {screen}
    </AppShell>
  );
}

export function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}
