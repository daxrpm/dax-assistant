import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import {
  DEFAULT_BASE_URL,
  getConnectionSettings,
  isTauri,
  resolveConnection,
  saveConnectionSettings,
  validateCurrentAuthorityHealth,
} from "../../api/connection";
import { AlertIcon, RefreshIcon } from "../../components/icons";
import { useWindowFrame } from "../../components/WindowFrame";
import {
  Badge,
  Button,
  Field,
  Panel,
  PanelBody,
  PanelHeader,
  SegmentedControl,
  Slider,
  TextInput,
  Toggle,
  useToast,
} from "../../design/primitives";
import type { ThemeMode } from "../../lib/useTheme";
import type { BackendStrategy } from "../../native/backend";
import { shutdownRealtimeStores } from "../../stores/realtime";
import { useI18n } from "../../i18n/I18n";
import p from "../page.module.css";
import { getAutostart, setAutostart, type AutostartState } from "../../native/autostart";
import {
  getNotifications,
  setNotifications,
  type NotificationState,
} from "../../native/notifications";
import {
  setMediaDuckingEnabled,
  setMediaDuckingLevel,
  useMediaDuckingEnabled,
  useMediaDuckingLevel,
} from "../../native/mediaDucking";
import {
  controlService,
  type ServiceAction,
  type ServiceStatus,
} from "../../native/service";
import { AuthorityRecovery } from "../../native/AuthorityRecovery";

/**
 * Desktop-only preferences (PLAN.md 6.4).
 *
 * Backend connection lives here rather than in Server, because Server edits the
 * backend's own bind address while this edits which backend *this client* talks
 * to. Conflating them is how you end up unable to reach the box you just moved.
 */
export function DesktopTab({
  themeMode,
  onThemeChange,
}: {
  themeMode: ThemeMode;
  onThemeChange: (next: ThemeMode) => void;
}) {
  const { locale, setLocale, t, text } = useI18n();
  const toast = useToast();
  const { frame, setFrame } = useWindowFrame();
  const initialConnection = getConnectionSettings();
  const [strategy, setStrategy] = useState<BackendStrategy>(initialConnection?.strategy ?? "local");
  const [localUrl, setLocalUrl] = useState(initialConnection?.local_url ?? DEFAULT_BASE_URL);
  const [remoteUrl, setRemoteUrl] = useState(initialConnection?.remote_url ?? "");
  const [checking, setChecking] = useState(false);
  const [health, setHealth] = useState<"unknown" | "ok" | "down">("unknown");
  const [version, setVersion] = useState<string | null>(null);
  const [autostart, setAutostartState] = useState<AutostartState | null>(null);
  const [notifications, setNotificationState] = useState<NotificationState | null>(null);
  const [nativeSaving, setNativeSaving] = useState(false);
  const [nodeService, setNodeService] = useState<ServiceStatus | null>(null);
  const [nodeServiceBusy, setNodeServiceBusy] = useState(false);
  const mediaDucking = useMediaDuckingEnabled();
  const mediaDuckingLevel = useMediaDuckingLevel();

  const probe = async () => {
    setChecking(true);
    try {
      validateCurrentAuthorityHealth(await api.health());
      const status = await api.status();
      setVersion(`${status.name} ${status.version}`);
      setHealth("ok");
    } catch (err) {
      setHealth("down");
      setVersion(null);
      if (!(err instanceof ApiError && err.isUnreachable)) {
        toast.show(err instanceof Error ? err.message : "Probe failed", "danger");
      }
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    void probe();
    void Promise.all([getAutostart(), getNotifications()])
      .then(([nextAutostart, nextNotifications]) => {
        setAutostartState(nextAutostart);
        setNotificationState(nextNotifications);
      })
      .catch((err) => toast.show(err instanceof Error ? err.message : String(err), "danger"));
    if (isTauri()) void runNodeServiceAction("status", false);
    // Probing once on mount is enough; the button covers manual re-checks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runNodeServiceAction = async (action: ServiceAction, reportError = true) => {
    setNodeServiceBusy(true);
    try {
      setNodeService(await controlService("capability_node", action));
    } catch (err) {
      setNodeService(null);
      if (reportError) toast.show(err instanceof Error ? err.message : String(err), "danger");
    } finally {
      setNodeServiceBusy(false);
    }
  };

  const changeAutostart = async (enabled: boolean) => {
    setNativeSaving(true);
    try {
      setAutostartState(await setAutostart(enabled));
    } catch (err) {
      toast.show(err instanceof Error ? err.message : String(err), "danger");
    } finally {
      setNativeSaving(false);
    }
  };

  const changeNotifications = async (enabled: boolean) => {
    setNativeSaving(true);
    try {
      const next = await setNotifications(enabled);
      setNotificationState(next);
      if (enabled && next.available && !next.enabled) {
        toast.show(t("settings.desktop.notificationDenied"), "danger");
      }
    } catch (err) {
      toast.show(err instanceof Error ? err.message : String(err), "danger");
    } finally {
      setNativeSaving(false);
    }
  };

  const changeWindowFrame = async (next: "native" | "custom") => {
    setNativeSaving(true);
    try {
      await setFrame(next);
    } catch (err) {
      toast.show(err instanceof Error ? err.message : String(err), "danger");
    } finally {
      setNativeSaving(false);
    }
  };

  const applyConnection = async () => {
    try {
      shutdownRealtimeStores();
      await saveConnectionSettings({
        strategy,
        localUrl: localUrl.trim() || DEFAULT_BASE_URL,
        remoteUrl: strategy === "local" ? null : remoteUrl,
        onboardingComplete: true,
      });
      await resolveConnection(false, shutdownRealtimeStores);
      toast.show(text("Conexión guardada; reiniciando el flujo seguro", "Connection saved; restarting the secure flow"), "success");
      window.location.reload();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Invalid backend URL", "danger");
    }
  };

  const reevaluate = async () => {
    setChecking(true);
    try {
      const result = await resolveConnection(false, shutdownRealtimeStores);
      toast.show(result.healthy ? result.active_url : t("settings.desktop.unreachable"), result.healthy ? "success" : "danger");
      if (result.changed) setTimeout(() => window.location.reload(), 300);
    } catch (err) {
      toast.show(err instanceof Error ? err.message : String(err), "danger");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title={t("settings.desktop.connection")}
          subtitle={t("settings.desktop.connectionSubtitle")}
          actions={
            <div className={p.actions}>
              <Badge
                tone={health === "ok" ? "success" : health === "down" ? "danger" : "neutral"}
                dot
              >
                {health === "ok" ? t("settings.desktop.reachable") : health === "down" ? t("settings.desktop.unreachable") : t("common.unknown")}
              </Badge>
              <Button size="sm" variant="ghost" loading={checking} onClick={() => void probe()}>
                <RefreshIcon size={13} />
                {t("settings.desktop.check")}
              </Button>
            </div>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <Field label={text("Autoridad", "Authority")} description={text("Elige una sola autoridad. Las capacidades locales para un servidor se conectan mediante dax edge, no mediante fallback.", "Choose one authority. Local capabilities for a server connect through dax edge, not through fallback.")}>
              {() => (
                <SegmentedControl
                  value={strategy}
                  onChange={setStrategy}
                  items={[
                    { id: "local", label: text("Local", "Local") },
                    { id: "remote", label: text("Servidor", "Server") },
                  ]}
                />
              )}
            </Field>
            {strategy === "local" && (
              <Field
                label={text("URL local", "Local URL")}
                description={version ? t("settings.desktop.connectedTo", { version }) : t("settings.desktop.defaultUrl")}
              >
                {(id) => (
                  <div className={p.actions}>
                    <TextInput
                      id={id}
                      className={p.grow}
                      value={localUrl}
                      onChange={(e) => setLocalUrl(e.target.value)}
                    />
                  </div>
                )}
              </Field>
            )}
            {strategy !== "local" && (
              <Field label={text("URL del servidor", "Server URL")} description={text("HTTPS obligatorio salvo loopback explícito.", "HTTPS is required except for explicit loopback.")}>
                {(id) => <TextInput id={id} value={remoteUrl} onChange={(event) => setRemoteUrl(event.target.value)} />}
              </Field>
            )}
            <div className={p.actions}>
              <Button variant="primary" onClick={() => void applyConnection()}>{t("settings.desktop.apply")}</Button>
              <Button variant="secondary" loading={checking} onClick={() => void reevaluate()}>{text("Reevaluar ahora", "Re-evaluate now")}</Button>
              <Button variant="ghost" onClick={() => window.dispatchEvent(new Event("dax:open-onboarding"))}>{text("Abrir onboarding", "Open onboarding")}</Button>
            </div>

            <div className={p.notice}>
              <span className={p.noticeIcon}>
                <AlertIcon size={14} />
              </span>
              <span>{text("Los backends remotos deben usar HTTPS (y WSS para sockets). La CSP incluida ya permite ambos; el backend debe autorizar explícitamente el origen ", "Remote backends must use HTTPS (and WSS for sockets). The bundled CSP already allows both; the backend must explicitly allow the ")}<code>tauri://localhost</code>{text(" en CORS.", " CORS origin.")}</span>
            </div>
            <div className={p.notice}>
              <span className={p.noticeIcon}><AlertIcon size={14} /></span>
              <span>{text("Recuperación manual solo para un backend reemplazado deliberadamente en la misma URL. Borra la identidad fijada y obliga a autenticar otra vez.", "Manual recovery only for a backend deliberately replaced at the same URL. It clears the identity pin and forces authentication again.")}</span>
              <AuthorityRecovery onRecovered={() => window.location.reload()} />
            </div>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title={text("Nodo de capacidad del portátil", "Laptop capability node")}
          subtitle={text(
            "El servidor conserva chats, configuración y almacenamiento; este servicio solo aporta comandos y archivos locales mientras está conectado.",
            "The server retains chats, configuration, and storage; this service only contributes local commands and files while connected.",
          )}
          actions={nodeService?.load_state === "loaded" ? (
            <Badge tone={nodeService.active_state === "active" ? "success" : "neutral"} dot>
              {nodeService.active_state === "active" ? text("En línea", "Online") : text("Detenido", "Stopped")}
            </Badge>
          ) : undefined}
        />
        <PanelBody>
          <div className={p.rows}>
            {!isTauri() ? (
              <p className={p.hint}>{t("settings.desktop.nativeUnavailable")}</p>
            ) : nodeService?.load_state !== "loaded" ? (
              <div className={p.spread}>
                <p className={p.hint}>
                  {nodeService?.load_state === "not-found"
                    ? text("El servicio dax-assistant-node.service no está instalado.", "The dax-assistant-node.service service is not installed.")
                    : text("Comprueba si el servicio del nodo está instalado.", "Check whether the node service is installed.")}
                </p>
                <Button size="sm" variant="ghost" loading={nodeServiceBusy} onClick={() => void runNodeServiceAction("status")}>
                  {t("common.refresh")}
                </Button>
              </div>
            ) : (
              <>
                <div className={p.spread}>
                  <span className={p.dim}>dax-assistant-node.service</span>
                  <span className={p.mono}>{nodeService.active_state} ({nodeService.sub_state})</span>
                </div>
                <p className={p.hint}>
                  {text(
                    "Inscribe el portátil con el código de Dispositivos antes de iniciarlo. Dax nunca inicia este servicio automáticamente.",
                    "Enroll the laptop with the code under Devices before starting it. Dax never starts this service automatically.",
                  )}
                </p>
                <div className={p.actions}>
                  {nodeService.active_state === "active" ? (
                    <Button size="sm" variant="secondary" loading={nodeServiceBusy} onClick={() => void runNodeServiceAction("stop")}>
                      {text("Detener", "Stop")}
                    </Button>
                  ) : (
                    <Button size="sm" variant="primary" loading={nodeServiceBusy} onClick={() => void runNodeServiceAction("start")}>
                      {text("Iniciar", "Start")}
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" disabled={nodeServiceBusy} onClick={() => void runNodeServiceAction("restart")}>
                    {text("Reiniciar", "Restart")}
                  </Button>
                  <Button size="sm" variant="ghost" disabled={nodeServiceBusy} onClick={() => void runNodeServiceAction("status")}>
                    {t("common.refresh")}
                  </Button>
                </div>
              </>
            )}
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title={t("settings.desktop.integration")}
          subtitle={isTauri() ? t("settings.desktop.integrationSubtitle") : t("settings.desktop.nativeUnavailable")}
        />
        <PanelBody>
          <div className={p.rows}>
            <Field label={t("settings.desktop.autostart")} description={autostart && !autostart.available ? autostart.reason : t("settings.desktop.autostartDescription")}>
              {(id) => (
                <Toggle
                  id={id}
                  checked={autostart?.enabled ?? false}
                  disabled={nativeSaving || !autostart?.available}
                  onChange={(next) => void changeAutostart(next)}
                  aria-label={t("settings.desktop.autostart")}
                />
              )}
            </Field>
            <Field label={t("settings.desktop.notifications")} description={notifications && !notifications.available ? notifications.reason : t("settings.desktop.notificationsDescription")}>
              {(id) => (
                <Toggle
                  id={id}
                  checked={notifications?.enabled ?? false}
                  disabled={nativeSaving || !notifications?.available}
                  onChange={(next) => void changeNotifications(next)}
                  aria-label={t("settings.desktop.notifications")}
                />
              )}
            </Field>
            <Field
              label={t("settings.desktop.mediaDucking")}
              description={t("settings.desktop.mediaDuckingDescription")}
            >
              {(id) => (
                <Toggle
                  id={id}
                  checked={mediaDucking}
                  onChange={setMediaDuckingEnabled}
                  aria-label={t("settings.desktop.mediaDucking")}
                />
              )}
            </Field>
            <Field
              label={t("settings.desktop.mediaDuckingLevel")}
              description={t("settings.desktop.mediaDuckingLevelDescription")}
            >
              {(id) => (
                <Slider
                  id={id}
                  min={0.10}
                  max={1}
                  step={0.05}
                  value={mediaDuckingLevel}
                  disabled={!mediaDucking}
                  onChange={setMediaDuckingLevel}
                  format={(value) => `${Math.round(value * 100)}%`}
                />
              )}
            </Field>
            <Field
              label={t("settings.desktop.windowFrame")}
              description={isTauri() ? t("settings.desktop.windowFrameDescription") : t("settings.desktop.nativeUnavailable")}
            >
              {() => (
                <SegmentedControl
                  value={frame}
                  disabled={nativeSaving || !isTauri()}
                  onChange={(next) => void changeWindowFrame(next)}
                  items={[
                    { id: "native", label: t("settings.desktop.windowFrameNative") },
                    { id: "custom", label: t("settings.desktop.windowFrameCustom") },
                  ]}
                />
              )}
            </Field>
            <p className={p.hint}>{t("settings.desktop.windowFrameWayland")}</p>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title={t("settings.desktop.appearance")} />
        <PanelBody>
          <Field label={t("settings.desktop.theme")} description={t("settings.desktop.themeDescription")}>
            {() => (
              <SegmentedControl
                value={themeMode}
                onChange={onThemeChange}
                items={[
                  { id: "system", label: t("theme.system") },
                  { id: "light", label: t("theme.light") },
                  { id: "dark", label: t("theme.dark") },
                ]}
              />
            )}
          </Field>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title={t("language.label")} />
        <PanelBody>
          <Field label={t("language.label")} description={t("language.description")}>
            {() => (
              <SegmentedControl
                value={locale}
                onChange={setLocale}
                items={[
                  { id: "es", label: t("language.spanish") },
                  { id: "en", label: t("language.english") },
                ]}
              />
            )}
          </Field>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title={t("settings.desktop.runtime")} />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.spread}>
              <span className={p.dim}>{t("settings.desktop.environment")}</span>
              <span className={p.mono}>
                {isTauri() ? "Tauri webview" : "Browser (dev)"}
              </span>
            </div>
            <div className={p.spread}>
              <span className={p.dim}>{t("settings.desktop.tokenStorage")}</span>
              <span className={p.mono}>
                {isTauri() ? "OS keyring" : "sessionStorage (dev fallback)"}
              </span>
            </div>
            <p className={p.hint}>{text("Los atajos globales y la bandeja están activos en la aplicación instalada. Las acciones de voz de la bandeja se ejecutan en este cliente y usan la sesión bearer actual.", "Global shortcuts and tray controls are active in the installed app. Tray voice actions run in this client and use the current bearer session.")}</p>
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
