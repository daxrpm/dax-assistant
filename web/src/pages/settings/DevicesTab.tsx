import { useCallback, useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { Copy, Laptop, Link2, RefreshCw, ShieldOff, Smartphone, Trash2 } from "lucide-react";
import { api, type DeviceKind, type PairedDevice } from "../../api/client";
import { Badge, Modal, Panel, PanelHeader, useToast } from "../../components/ui";

export function DevicesTab() {
  const toast = useToast();
  const [devices, setDevices] = useState<PairedDevice[] | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [pairingUri, setPairingUri] = useState<string | null>(null);
  const [backendUrl, setBackendUrl] = useState<string | null>(null);
  const [pairingKind, setPairingKind] = useState<DeviceKind>("client");
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<{
    device: PairedDevice;
    action: "revoke" | "delete";
  } | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDevices((await api.devices()).devices);
    } catch (error) {
      setDevices((current) => current ?? []);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (expiresAt === null) return;
    const tick = () => {
      const next = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
      setRemaining(next);
      if (next === 0) {
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

  const pair = async (kind: DeviceKind) => {
    setBusy(`pair:${kind}`);
    try {
      const response = await api.pairDevice(kind);
      setCode(response.code);
      setPairingUri(response.pairing_uri);
      setBackendUrl(response.backend_url);
      setPairingKind(kind);
      setExpiresAt(Date.now() + response.expires_in_seconds * 1000);
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Pairing failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  const mutate = async (device: PairedDevice, action: "revoke" | "delete") => {
    setBusy(`${action}:${device.id}`);
    try {
      if (action === "revoke") await api.revokeDevice(device.id);
      else await api.deleteDevice(device.id);
      await refresh();
      toast.show(action === "revoke" ? `${device.name} revoked` : `${device.name} deleted`, "success");
    } catch (error) {
      toast.show(error instanceof Error ? error.message : `Could not ${action} device`, "danger");
    } finally {
      setBusy(null);
      setConfirming(null);
    }
  };

  const enrollmentCommand = code && backendUrl
    ? `dax edge enroll --server ${backendUrl} --code ${code} --name <name>`
    : null;

  const copyCommand = async () => {
    if (!enrollmentCommand) return;
    try {
      await navigator.clipboard.writeText(enrollmentCommand);
      toast.show("Enrollment command copied", "success");
    } catch {
      toast.show("Could not copy the enrollment command", "danger");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Panel>
        <PanelHeader
          title="Add a device"
          description="Client pairing and laptop capabilities are enrolled separately"
          action={
            <div className="flex flex-wrap justify-end gap-2">
              <Button size="sm" variant="secondary" onPress={() => pair("client")} isDisabled={busy !== null}>
                <Link2 size={14} />
                Pair a client
              </Button>
              <Button size="sm" variant="primary" onPress={() => pair("capability_node")} isDisabled={busy !== null}>
                <Laptop size={14} />
                Add laptop capability
              </Button>
            </div>
          }
        />
        <p className="mb-3 text-sm text-muted">
          The server remains authoritative. This laptop contributes local commands and files only while online; turning it off does not move chats, configuration, or storage.
        </p>
        {code ? (
          <div className="rounded-xl border border-accent/30 bg-accent-soft p-4 text-center">
            <p className="text-xs text-muted">
              {pairingKind === "client" ? "Enter this code on the new client" : "Run this command on the laptop"}
            </p>
            {pairingKind === "client" ? (
              <p className="my-3 break-all font-mono text-3xl font-semibold tracking-[0.25em]">{code}</p>
            ) : (
              <div className="my-3 flex min-w-0 flex-col items-stretch gap-2 rounded-lg bg-background/70 p-3 text-left sm:flex-row sm:items-start">
                <code className="min-w-0 flex-1 break-all text-xs">{enrollmentCommand}</code>
                <Button size="sm" variant="tertiary" onPress={copyCommand}>
                  <Copy size={14} /> Copy
                </Button>
              </div>
            )}
            <p className="text-xs text-muted">Expires in {remaining}s</p>
            {pairingKind === "client" && pairingUri && <p className="mt-2 break-all font-mono text-[10px] text-muted">{pairingUri}</p>}
          </div>
        ) : (
          <p className="text-sm text-muted">Pairing codes expire automatically and can only be redeemed once.</p>
        )}
      </Panel>

      <Panel>
        <PanelHeader
          title="Paired devices"
          description="Presence is live; revoked devices can no longer refresh access tokens"
          action={
            <Button size="sm" variant="tertiary" isIconOnly onPress={refresh} aria-label="Refresh devices">
              <RefreshCw size={14} />
            </Button>
          }
        />
        <div className="flex flex-col gap-2">
          {devices === null ? (
            <p className="text-sm text-muted">Loading devices…</p>
          ) : devices.length === 0 ? (
            <p className="text-sm text-muted">No devices paired.</p>
          ) : devices.map((device) => (
            <div key={device.id} className="flex min-w-0 flex-wrap items-center gap-3 rounded-xl border border-separator bg-background p-3 sm:flex-nowrap">
              {device.kind === "capability_node"
                ? <Laptop size={17} className="shrink-0 text-muted" />
                : <Smartphone size={17} className="shrink-0 text-muted" />}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate text-sm font-medium">{device.name}</span>
                  <Badge color={device.revoked ? "danger" : device.connected ? "success" : "default"}>
                    {device.revoked ? "Revoked" : device.connected ? "Connected" : "Offline"}
                  </Badge>
                  <Badge color="default">{device.kind === "capability_node" ? "Capability node" : "Client"}</Badge>
                </div>
                <p className="text-xs text-muted">
                  {device.platform}{device.last_seen_at ? ` · Last seen ${new Date(device.last_seen_at).toLocaleString()}` : " · Never connected"}
                </p>
              </div>
              {!device.revoked && (
                <Button
                  size="sm"
                  variant="tertiary"
                  isIconOnly
                  isDisabled={busy !== null}
                   onPress={() => setConfirming({ device, action: "revoke" })}
                  aria-label={`Revoke ${device.name}`}
                >
                  <ShieldOff size={14} />
                </Button>
              )}
              <Button
                size="sm"
                variant="tertiary"
                isIconOnly
                isDisabled={busy !== null}
                 onPress={() => setConfirming({ device, action: "delete" })}
                aria-label={`Delete ${device.name}`}
              >
                <Trash2 size={14} className="text-danger" />
              </Button>
            </div>
          ))}
        </div>
      </Panel>

      <Modal
        open={confirming !== null}
        onClose={() => setConfirming(null)}
        title={confirming?.action === "delete" ? "Delete device" : "Revoke device"}
        footer={confirming && (
          <>
            <Button variant="tertiary" onPress={() => setConfirming(null)}>Cancel</Button>
            <Button
              variant="danger"
              isDisabled={busy !== null}
              onPress={() => mutate(confirming.device, confirming.action)}
            >
              {confirming.action === "delete" ? "Delete" : "Revoke"}
            </Button>
          </>
        )}
      >
        <p className="text-sm text-muted">
          {confirming && `${confirming.action === "delete" ? "Deleting" : "Revoking"} “${confirming.device.name}” cuts off its access. Chats, configuration, and storage remain on the server.`}
        </p>
      </Modal>
    </div>
  );
}
