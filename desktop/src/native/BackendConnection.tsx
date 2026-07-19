import { useState } from "react";
import { resolveConnection } from "../api/connection";
import { Button } from "../design/primitives";
import { useI18n } from "../i18n/I18n";
import s from "./BackendConnection.module.css";

export function BackendConnection({
  error,
  onRetry,
  onConfigure,
}: {
  error?: string | null;
  onRetry: () => void;
  onConfigure: () => void;
}) {
  const { t, text } = useI18n();
  const [message, setMessage] = useState(error ?? "");
  const [busy, setBusy] = useState(false);

  const reevaluate = async () => {
    setBusy(true);
    try {
      const result = await resolveConnection(false);
      setMessage(
        result.healthy
          ? text(`Backend seleccionado: ${result.active_url}`, `Selected backend: ${result.active_url}`)
          : text("Ningún candidato responde.", "No candidate is responding."),
      );
      if (result.healthy) onRetry();
    } catch (nextError) {
      setMessage(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={s.card} aria-label={t("backend.connection")}>
      <div>
        <h1 className={s.title}>{t("backend.title")}</h1>
        <p className={s.message} role="alert">{message || t("backend.failed")}</p>
      </div>
      <p className={s.message}>{text("Puedes volver a probar la estrategia actual, buscar su fallback o cambiar la configuración.", "Retry the current strategy, evaluate its fallback, or change the configuration.")}</p>
      <div className={s.actions}>
        <Button variant="primary" onClick={onRetry}>{t("common.retry")}</Button>
        <Button loading={busy} onClick={() => void reevaluate()}>{text("Reevaluar fallback", "Re-evaluate fallback")}</Button>
        <Button variant="ghost" onClick={onConfigure}>{text("Cambiar estrategia", "Change strategy")}</Button>
      </div>
    </section>
  );
}
