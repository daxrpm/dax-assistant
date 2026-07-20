import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  useRef,
} from "react";
import { ApiError, api } from "./api/client";
import {
  clearToken,
  getConnectionSettings,
  loadConnectionSettings,
  resolveConnection,
  validateCurrentAuthorityHealth,
} from "./api/connection";
import type { AuthStatus } from "./api/types";
import { permitsAuthenticatedShell } from "./authState";
import { AppShell } from "./components/AppShell";
import { CommandDeck } from "./components/CommandDeck";
import { WindowFrame } from "./components/WindowFrame";
import {
  CommandPalette,
  usePaletteShortcut,
  type PaletteAction,
} from "./components/CommandPalette";
import { Spinner, ToastProvider, useToast } from "./design/primitives";
import { useHashRoute } from "./lib/useHashRoute";
import { useTheme } from "./lib/useTheme";
import { useI18n } from "./i18n/I18n";
import { BackendConnection } from "./native/BackendConnection";
import { Onboarding } from "./native/Onboarding";
import { VoiceHud } from "./native/VoiceHud";
import { MediaDuckingBridge } from "./native/mediaDucking";
import { desktopRuntime, isTauriRuntime } from "./native/runtime";
import {
  createDisconnectMonitor,
  sendNativeNotification,
} from "./native/notifications";
import { shutdownRealtimeStores } from "./stores/realtime";
import { Commands } from "./screens/Commands";
import { Login } from "./screens/Login";
import s from "./App.module.css";

const Chat = lazy(() => import("./screens/Chat").then((module) => ({ default: module.Chat })));
const Logs = lazy(() => import("./screens/Logs").then((module) => ({ default: module.Logs })));
const Marketplace = lazy(() =>
  import("./screens/Marketplace").then((module) => ({ default: module.Marketplace })),
);
const Mcp = lazy(() => import("./screens/Mcp").then((module) => ({ default: module.Mcp })));
const Settings = lazy(() =>
  import("./screens/Settings").then((module) => ({ default: module.Settings })),
);

type Phase = "booting" | "onboarding" | "unauthenticated" | "authenticated" | "unreachable";

function AppInner() {
  const [phase, setPhase] = useState<Phase>("booting");
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  // The app opens on the command deck, not on a screen (PLAN.md 5.0).
  const [route, navigate] = useHashRoute("/");
  const { mode, setMode } = useTheme();
  const { locale, setLocale, t } = useI18n();
  const toast = useToast();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const authCheckGeneration = useRef(0);

  const openOnboarding = useCallback(() => {
    authCheckGeneration.current += 1;
    setPhase("onboarding");
  }, []);

  const togglePalette = useCallback(() => setPaletteOpen((open) => !open), []);
  usePaletteShortcut(togglePalette);

  const checkAuth = useCallback(async (resolveBackend = true) => {
    const generation = ++authCheckGeneration.current;
    try {
      const settings = resolveBackend
        ? await loadConnectionSettings()
        : getConnectionSettings();
      if (settings && !settings.onboarding_complete) {
        setPhase("onboarding");
        return;
      }
      if (resolveBackend) {
        const resolution = await resolveConnection(false, shutdownRealtimeStores);
        if (generation !== authCheckGeneration.current) return;
        if (!resolution.healthy) {
          setBootError(t("backend.failed"));
          setPhase("unreachable");
          return;
        }
      }
      const status = await api.authStatus();
      if (generation !== authCheckGeneration.current) return;
      setAuthStatus(status);
      setPhase(
        !status.auth_enabled || status.authenticated
          ? "authenticated"
          : "unauthenticated",
      );
      setBootError(null);
    } catch (err) {
      if (generation !== authCheckGeneration.current) return;
      setAuthStatus(null);
      if (err instanceof ApiError && err.isUnreachable) {
        setBootError(err.message);
        setPhase("unreachable");
        return;
      }
      setBootError(err instanceof Error ? err.message : String(err));
      setPhase("unauthenticated");
    }
  }, [t]);

  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    window.addEventListener("dax:open-onboarding", openOnboarding);
    return () => window.removeEventListener("dax:open-onboarding", openOnboarding);
  }, [openOnboarding]);

  useEffect(() => {
    if (!isTauriRuntime() || phase !== "authenticated") return;
    const monitor = createDisconnectMonitor({
      probe: async () => {
        try {
          return validateCurrentAuthorityHealth(await api.health());
        } catch (error) {
          await clearToken();
          throw error;
        }
      },
      notify: () =>
        sendNativeNotification(
          "Dax backend disconnected",
          "The backend has not responded to three consecutive health checks.",
        ),
    });
    const timer = window.setInterval(() => void monitor.check(), 15_000);
    return () => window.clearInterval(timer);
  }, [checkAuth, phase]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Signing out locally matters more than the server round-trip.
    }
    try {
      await clearToken();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : String(err), "danger");
      return;
    }
    shutdownRealtimeStores();
    setPhase("unauthenticated");
    void checkAuth();
  }, [checkAuth, toast]);

  /**
   * Verbs, as opposed to destinations. They live in the palette because the
   * deck's side panels are glanceable, not navigable (PLAN.md 5.0) — putting a
   * theme switcher in one of them would make it a control surface.
   */
  const paletteActions = useMemo<PaletteAction[]>(
    () => [
      {
        id: "voice:on",
        label: t("palette.voiceOn"),
        hint: "voice/toggle",
        group: t("common.actions"),
        run: () => void api.toggleVoice(true).catch(() => undefined),
      },
      {
        id: "voice:off",
        label: t("palette.voiceOff"),
        hint: "voice/toggle",
        group: t("common.actions"),
        run: () => void api.toggleVoice(false).catch(() => undefined),
      },
      {
        id: "theme",
        label: t("palette.theme"),
        hint: mode,
        group: t("common.actions"),
        run: () => setMode(mode === "dark" ? "light" : mode === "light" ? "system" : "dark"),
      },
      {
        id: "language",
        label: locale === "es" ? t("language.change") : t("language.change.es"),
        hint: locale === "es" ? "EN" : "ES",
        group: t("common.actions"),
        run: () => setLocale(locale === "es" ? "en" : "es"),
      },
      {
        id: "logout",
        label: t("palette.logout"),
        group: t("common.actions"),
        run: () => void logout(),
      },
    ],
    [locale, logout, mode, setLocale, setMode, t],
  );

  if (phase === "booting") {
    return (
      <div className={s.center}>
        <Spinner size={20} />
      </div>
    );
  }

  if (phase === "onboarding") {
    const settings = getConnectionSettings();
    return settings ? (
      <Onboarding initial={settings} onComplete={() => void checkAuth(false)} />
    ) : null;
  }

  if (phase === "unreachable") {
    return (
      <div className={s.center}>
        <BackendConnection
          error={bootError}
          onRetry={() => void checkAuth()}
          onConfigure={openOnboarding}
        />
      </div>
    );
  }

  if (phase === "unauthenticated") {
    return authStatus ? (
      <Login status={authStatus} onAuthenticated={() => void checkAuth()} />
    ) : (
      <div className={s.center}>
        <BackendConnection
          error={bootError}
          onRetry={() => void checkAuth()}
          onConfigure={openOnboarding}
        />
      </div>
    );
  }

  if (!permitsAuthenticatedShell(authStatus)) {
    return (
      <div className={s.center}>
        <BackendConnection
          error={bootError}
          onRetry={() => void checkAuth()}
          onConfigure={openOnboarding}
        />
      </div>
    );
  }

  // Screens that lay out their own full-height chrome opt out of the shell's
  // padded scroll container.
  const BARE_ROUTES = ["/chat", "/logs", "/settings"];

  const palette = (
    <CommandPalette
      open={paletteOpen}
      onClose={() => setPaletteOpen(false)}
      onNavigate={navigate}
      extraActions={paletteActions}
    />
  );

  const contentRoutes = ["/chat", "/mcp", "/marketplace", "/commands", "/logs", "/settings"];
  // Unknown hashes fall back to the command deck rather than an otherwise hidden dashboard.
  const isDeck = route === "/" || route === "" || !contentRoutes.includes(route);

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
    ) : null;

  return (
    <>
      <MediaDuckingBridge />
      {isDeck ? (
        <CommandDeck onOpenPalette={() => setPaletteOpen(true)} />
      ) : (
        <AppShell
          route={route}
          onNavigate={navigate}
          onOpenPalette={() => setPaletteOpen(true)}
          themeMode={mode}
          onCycleTheme={setMode}
          onLogout={() => void logout()}
          bare={BARE_ROUTES.includes(route)}
        >
          <Suspense fallback={<div className={s.center}><Spinner size={20} /></div>}>
            {screen}
          </Suspense>
        </AppShell>
      )}
      {palette}
    </>
  );
}

export function App() {
  const windowKind = new URLSearchParams(window.location.search).get("window");
  const isHud = windowKind === "hud" || windowKind === "voice-hud";
  useEffect(() => {
    if (isTauriRuntime() && !isHud) void desktopRuntime.start(true);
  }, [isHud]);
  if (isHud) {
    return <HudApp />;
  }
  return (
    <WindowFrame>
      <ToastProvider>
        <DesktopRuntimeError />
        <AppInner />
      </ToastProvider>
    </WindowFrame>
  );
}

function DesktopRuntimeError() {
  const runtime = useSyncExternalStore(
    desktopRuntime.subscribe,
    desktopRuntime.getSnapshot,
    desktopRuntime.getSnapshot,
  );
  const toast = useToast();
  useEffect(() => {
    if (runtime.pttError) toast.show(runtime.pttError, "danger");
  }, [runtime.pttError, toast]);
  return null;
}

function HudApp() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    void loadConnectionSettings()
      .then(() => resolveConnection(false, shutdownRealtimeStores))
      .then(() => setReady(true));
  }, []);
  return ready ? <VoiceHud /> : null;
}
