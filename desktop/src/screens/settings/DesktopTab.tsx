import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import {
  DEFAULT_BASE_URL,
  getBaseUrl,
  isTauri,
  setBaseUrl,
} from "../../api/connection";
import { AlertIcon, RefreshIcon } from "../../components/icons";
import {
  Badge,
  Button,
  Field,
  Panel,
  PanelBody,
  PanelHeader,
  SegmentedControl,
  TextInput,
  useToast,
} from "../../design/primitives";
import type { ThemeMode } from "../../lib/useTheme";
import p from "../page.module.css";

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
  const toast = useToast();
  const [url, setUrl] = useState(getBaseUrl());
  const [checking, setChecking] = useState(false);
  const [health, setHealth] = useState<"unknown" | "ok" | "down">("unknown");
  const [version, setVersion] = useState<string | null>(null);

  const probe = async () => {
    setChecking(true);
    try {
      await api.health();
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
    // Probing once on mount is enough; the button covers manual re-checks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyUrl = () => {
    setBaseUrl(url.trim() || DEFAULT_BASE_URL);
    toast.show("Backend URL saved — reloading", "success");
    // Every open socket points at the old origin, so a reload is the honest way
    // to re-establish them rather than reconnecting each one by hand.
    setTimeout(() => window.location.reload(), 600);
  };

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="Backend connection"
          subtitle="Which Dax instance this app talks to"
          actions={
            <div className={p.actions}>
              <Badge
                tone={health === "ok" ? "success" : health === "down" ? "danger" : "neutral"}
                dot
              >
                {health === "ok" ? "Reachable" : health === "down" ? "Unreachable" : "Unknown"}
              </Badge>
              <Button size="sm" variant="ghost" loading={checking} onClick={() => void probe()}>
                <RefreshIcon size={13} />
                Check
              </Button>
            </div>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <Field
              label="Base URL"
              description={version ? `Connected to ${version}` : "Default is http://127.0.0.1:8420"}
            >
              {(id) => (
                <div className={p.actions}>
                  <TextInput
                    id={id}
                    className={p.grow}
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                  <Button
                    variant="secondary"
                    disabled={url.trim() === getBaseUrl()}
                    onClick={applyUrl}
                  >
                    Apply
                  </Button>
                </div>
              )}
            </Field>

            <div className={p.notice}>
              <span className={p.noticeIcon}>
                <AlertIcon size={14} />
              </span>
              <span>
                Pointing at a <strong>remote</strong> host also requires editing the
                bundled CSP: <code>connect-src</code> is baked in at build time and
                currently allows loopback only. The backend must additionally list{" "}
                <code>tauri://localhost</code> and <code>http://tauri.localhost</code> in
                its CORS origins.
              </span>
            </div>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Appearance" />
        <PanelBody>
          <Field label="Theme" description="System follows your desktop's light/dark setting.">
            {() => (
              <SegmentedControl
                value={themeMode}
                onChange={onThemeChange}
                items={[
                  { id: "system", label: "System" },
                  { id: "light", label: "Light" },
                  { id: "dark", label: "Dark" },
                ]}
              />
            )}
          </Field>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Runtime" />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.spread}>
              <span className={p.dim}>Environment</span>
              <span className={p.mono}>
                {isTauri() ? "Tauri webview" : "Browser (dev)"}
              </span>
            </div>
            <div className={p.spread}>
              <span className={p.dim}>Session token storage</span>
              <span className={p.mono}>
                {isTauri() ? "OS keyring" : "sessionStorage (dev fallback)"}
              </span>
            </div>
            <p className={p.hint}>
              Global hotkey, autostart, tray behavior and notification preferences arrive
              with packaging in M6.
            </p>
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
