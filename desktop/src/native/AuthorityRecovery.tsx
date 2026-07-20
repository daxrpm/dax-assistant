import { useState } from "react";
import {
  getConnectionSettings,
  isTauri,
  recoverSameOriginAuthorityReplacement,
} from "../api/connection";
import { Button, Modal } from "../design/primitives";
import { useI18n } from "../i18n/I18n";
import { shutdownRealtimeStores } from "../stores/realtime";

export function AuthorityRecovery({ onRecovered }: { onRecovered: () => void }) {
  const { text } = useI18n();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const settings = getConnectionSettings();

  if (!isTauri() || !settings?.active_server_id) return null;

  const recover = async () => {
    setBusy(true);
    setError("");
    try {
      shutdownRealtimeStores();
      const result = await recoverSameOriginAuthorityReplacement();
      if (!result.healthy) {
        setError(text("La autoridad de reemplazo todavía no responde.", "The replacement authority is still unreachable."));
        return;
      }
      onRecovered();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button variant="destructive" onClick={() => setConfirming(true)}>
        {text("Reemplazar autoridad en este origen", "Replace authority at this origin")}
      </Button>
      <Modal
        open={confirming}
        onClose={busy ? undefined : () => setConfirming(false)}
        title={text("Confirmar reemplazo de autoridad", "Confirm authority replacement")}
        footer={(
          <>
            <Button disabled={busy} onClick={() => setConfirming(false)}>{text("Cancelar", "Cancel")}</Button>
            <Button variant="destructive" loading={busy} onClick={() => void recover()}>
              {text("Borrar identidad y credenciales", "Clear identity and credentials")}
            </Button>
          </>
        )}
      >
        <p>{text(
          "Solo continúa si reemplazaste deliberadamente el backend en este mismo origen. Dax borrará la identidad fijada y todas las credenciales de la autoridad anterior, volverá a comprobar la salud y exigirá iniciar sesión de nuevo. Nunca confiará en la identidad nueva de forma silenciosa.",
          "Continue only if you deliberately replaced the backend at this same origin. Dax will clear the pinned identity and every credential for the old authority, check health again, and require a new sign-in. It will never trust the new identity silently.",
        )}</p>
        <p><code>{settings.active_url}</code><br /><code>{settings.active_server_id}</code></p>
        {error && <p role="alert">{error}</p>}
      </Modal>
    </>
  );
}
