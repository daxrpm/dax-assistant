import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { PairedDevice } from "../api/types";
import { useI18n } from "../i18n/I18n";
import s from "./PairedDevices.module.css";

/**
 * Paired phones, and the code that pairs a new one.
 *
 * This is deliberately on the deck rather than buried in settings. The phone is
 * a peer client, not a preference: when it attaches, that is a fact about the
 * running system in the same way the voice pipeline or an MCP server is, and it
 * belongs where the other live facts are.
 *
 * Presence is polled rather than pushed. A dedicated socket for one boolean
 * would be the wrong trade, and a few seconds of staleness on "is my phone
 * connected" costs nothing — the code is shown for minutes, and the connection
 * either holds or it does not.
 */
export function PairedDevices() {
  const { t } = useI18n();
  const [devices, setDevices] = useState<PairedDevice[] | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const response = await api.devices();
      if (mounted.current) setDevices(response.devices);
    } catch {
      // A failed poll is not worth surfacing: the next one is seconds away and
      // an error banner that flickers on every hiccup trains people to ignore
      // banners.
      if (mounted.current) setDevices((current) => current ?? []);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  // The countdown is the honest part of the UI: a code that has silently
  // expired while on screen is worse than no code.
  useEffect(() => {
    if (expiresAt === null) return;
    const tick = () => {
      const left = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
      setRemaining(left);
      if (left === 0) {
        setCode(null);
        setExpiresAt(null);
      }
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  async function pair() {
    setBusy(true);
    setError(null);
    try {
      const response = await api.pairDevice();
      setCode(response.code);
      setExpiresAt(Date.now() + response.expires_in_seconds * 1000);
    } catch {
      setError(t("devices.pairFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(device: PairedDevice) {
    setBusy(true);
    try {
      await api.revokeDevice(device.id);
      await refresh();
    } catch {
      setError(t("devices.revokeFailed"));
    } finally {
      setBusy(false);
    }
  }

  const active = (devices ?? []).filter((device) => !device.revoked);

  return (
    <div className={s.wrap}>
      {code ? (
        <div className={s.codeCard}>
          <span className={s.codeLabel}>{t("devices.enterOnPhone")}</span>
          {/* Spaced and oversized because it is transcribed by hand from one
              screen to another; the pairing alphabet already excludes O/0 and
              I/1. */}
          <span className={s.code}>{code.split("").join(" ")}</span>
          <span className={s.codeExpiry}>
            {t("devices.expiresIn").replace("{s}", String(remaining))}
          </span>
        </div>
      ) : (
        <button type="button" className={s.pairButton} onClick={pair} disabled={busy}>
          {busy ? t("devices.pairing") : t("devices.pair")}
        </button>
      )}

      {error && <p className={s.error}>{error}</p>}

      {devices === null ? (
        <p className={s.empty}>{t("common.loading")}</p>
      ) : active.length === 0 ? (
        <p className={s.empty}>{t("devices.none")}</p>
      ) : (
        <ul className={s.list}>
          {active.map((device) => (
            <li key={device.id} className={s.item}>
              <span
                className={`${s.led} ${device.connected ? s.ledLive : s.ledOff}`}
                aria-hidden="true"
              />
              <span className={s.itemBody}>
                <span className={s.itemName}>{device.name}</span>
                <span className={s.itemMeta}>
                  {device.connected
                    ? t("devices.connected")
                    : device.last_seen_at
                      ? t("devices.lastSeen").replace(
                          "{when}",
                          new Date(device.last_seen_at).toLocaleString(),
                        )
                      : t("devices.neverConnected")}
                </span>
              </span>
              <button
                type="button"
                className={s.revoke}
                onClick={() => void revoke(device)}
                disabled={busy}
                title={t("devices.revokeHint")}
              >
                {t("devices.revoke")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
