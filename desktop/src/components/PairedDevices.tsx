import { useCallback, useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

import { api } from "../api/client";
import type { DeviceKind, PairedDevice } from "../api/types";
import { Button, Modal } from "../design/primitives";
import { useI18n } from "../i18n/I18n";
import s from "./PairedDevices.module.css";

/**
 * Paired clients and capability nodes, and the code that pairs a new one.
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
  const { t, text } = useI18n();
  const [devices, setDevices] = useState<PairedDevice[] | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [pairingUri, setPairingUri] = useState<string | null>(null);
  const [backendUrl, setBackendUrl] = useState<string | null>(null);
  const [pairingKind, setPairingKind] = useState<DeviceKind>("client");
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<{
    device: PairedDevice;
    action: "revoke" | "delete";
  } | null>(null);
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
        setPairingUri(null);
        setBackendUrl(null);
        setExpiresAt(null);
      }
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  async function pair(kind: DeviceKind) {
    setBusy(true);
    setError(null);
    try {
      const response = await api.pairDevice(kind);
      setCode(response.code);
      setPairingUri(response.pairing_uri);
      setBackendUrl(response.backend_url);
      setPairingKind(kind);
      setExpiresAt(Date.now() + response.expires_in_seconds * 1000);
    } catch {
      setError(t("devices.pairFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function mutate(device: PairedDevice, action: "revoke" | "delete") {
    setBusy(true);
    setError(null);
    try {
      if (action === "revoke") await api.revokeDevice(device.id);
      else await api.deleteDevice(device.id);
      await refresh();
    } catch {
      setError(
        action === "revoke"
          ? t("devices.revokeFailed")
          : text("No se pudo eliminar el dispositivo", "Could not delete the device"),
      );
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  const enrollmentCommand = code && backendUrl
    ? `dax edge enroll --server ${backendUrl} --code ${code} --name <name>`
    : null;

  async function copyCommand() {
    if (!enrollmentCommand) return;
    try {
      await navigator.clipboard.writeText(enrollmentCommand);
    } catch {
      setError(text("No se pudo copiar el comando", "Could not copy the command"));
    }
  }

  return (
    <div className={s.wrap}>
      <p className={s.model}>
        {text(
          "El servidor sigue siendo la autoridad. Los nodos solo aportan capacidades del dispositivo mientras están conectados; desactivarlos no mueve chats, configuración ni almacenamiento.",
          "The server remains authoritative. Nodes contribute device capabilities only while online; turning them off does not move chats, configuration, or storage.",
        )}
      </p>

      {code ? (
        <div className={s.codeCard}>
          <span className={s.codeLabel}>
            {pairingKind === "client"
              ? t("devices.enterOnPhone")
              : text("Inscribir un dispositivo como nodo", "Enroll a device as a node")}
          </span>
          {pairingUri && (
            <div className={s.qr} aria-label={t("devices.scanQr")}>
              <QRCodeSVG
                value={pairingUri}
                size={144}
                level="M"
                marginSize={1}
                bgColor="#ffffff"
                fgColor="#0a0f18"
              />
            </div>
          )}
          <span className={s.or}>{t("devices.orCode")}</span>
          <span className={s.code}>{code.split("").join(" ")}</span>
          {pairingKind === "capability_node" && (
            <div className={s.commandRow}>
              <code className={s.command}>{enrollmentCommand}</code>
              <button type="button" className={s.revoke} onClick={() => void copyCommand()}>
                {text("Copiar", "Copy")}
              </button>
            </div>
          )}
          <span className={s.codeExpiry}>
            {t("devices.expiresIn").replace("{s}", String(remaining))}
          </span>
        </div>
      ) : (
        <div className={s.pairActions}>
          <button type="button" className={s.pairButton} onClick={() => void pair("client")} disabled={busy}>
            {busy ? t("devices.pairing") : t("devices.pair")}
          </button>
          <button type="button" className={s.pairButton} onClick={() => void pair("capability_node")} disabled={busy}>
            {text("Añadir nodo de capacidad", "Add capability node")}
          </button>
        </div>
      )}

      {error && <p className={s.error}>{error}</p>}

      {devices === null ? (
        <p className={s.empty}>{t("common.loading")}</p>
      ) : devices.length === 0 ? (
        <p className={s.empty}>{t("devices.none")}</p>
      ) : (
        <ul className={s.list}>
          {devices.map((device) => (
            <li key={device.id} className={s.item}>
              <span
                className={`${s.led} ${device.connected && !device.revoked ? s.ledLive : s.ledOff}`}
                aria-hidden="true"
              />
              <span className={s.itemBody}>
                <span className={s.itemName}>{device.name}</span>
                <span className={s.itemMeta}>
                  {device.kind === "capability_node"
                    ? text("Nodo de capacidad", "Capability node")
                    : text("Cliente", "Client")}
                  {" · "}
                  {device.revoked
                    ? text("revocado", "revoked")
                    : device.connected
                    ? t("devices.connected")
                    : device.last_seen_at
                      ? t("devices.lastSeen").replace(
                          "{when}",
                          new Date(device.last_seen_at).toLocaleString(),
                        )
                      : t("devices.neverConnected")}
                </span>
              </span>
              <span className={s.itemActions}>
                {!device.revoked && (
                  <button
                    type="button"
                    className={s.revoke}
                    onClick={() => setConfirming({ device, action: "revoke" })}
                    disabled={busy}
                    title={t("devices.revokeHint")}
                  >
                    {t("devices.revoke")}
                  </button>
                )}
                <button
                  type="button"
                  className={s.revoke}
                  onClick={() => setConfirming({ device, action: "delete" })}
                  disabled={busy}
                >
                  {t("common.delete")}
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={confirming !== null}
        title={confirming?.action === "delete"
          ? text("Eliminar dispositivo", "Delete device")
          : text("Revocar dispositivo", "Revoke device")}
        onClose={() => setConfirming(null)}
        footer={confirming && (
          <>
            <Button variant="ghost" onClick={() => setConfirming(null)}>{t("common.cancel")}</Button>
            <Button
              variant="destructive"
              loading={busy}
              onClick={() => void mutate(confirming.device, confirming.action)}
            >
              {confirming.action === "delete" ? t("common.delete") : t("devices.revoke")}
            </Button>
          </>
        )}
      >
        {confirming && text(
          `${confirming.action === "delete" ? "Eliminar" : "Revocar"} “${confirming.device.name}” corta su acceso. Esta acción no mueve conversaciones ni configuración.`,
          `${confirming.action === "delete" ? "Deleting" : "Revoking"} “${confirming.device.name}” cuts off its access. This does not move conversations or configuration.`,
        )}
      </Modal>
    </div>
  );
}
