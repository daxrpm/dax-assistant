import { useState } from "react";
import {
  DEFAULT_BASE_URL,
  resolveConnection,
  saveConnectionSettings,
  validateBaseUrl,
} from "../api/connection";
import { Button, TextInput } from "../design/primitives";
import { useI18n } from "../i18n/I18n";
import { shutdownRealtimeStores } from "../stores/realtime";
import type { BackendSettings, BackendStrategy } from "./backend";
import { controlService, type ServiceStatus } from "./service";
import s from "./Onboarding.module.css";

export const ONBOARDING_STEPS = 5;

export function canAdvanceOnboarding(
  step: number,
  strategy: BackendStrategy,
  localUrl: string,
  remoteUrl: string,
): boolean {
  if (step !== 2) return true;
  try {
    validateBaseUrl(localUrl, true);
    if (strategy !== "local") validateBaseUrl(remoteUrl);
    return true;
  } catch {
    return false;
  }
}

export function Onboarding({
  initial,
  onComplete,
}: {
  initial: BackendSettings;
  onComplete: () => void;
}) {
  const { text } = useI18n();
  const [step, setStep] = useState(0);
  const [strategy, setStrategy] = useState<BackendStrategy>(initial.strategy);
  const [localUrl, setLocalUrl] = useState(initial.local_url || DEFAULT_BASE_URL);
  const [remoteUrl, setRemoteUrl] = useState(initial.remote_url ?? "");
  const [allowStart, setAllowStart] = useState(false);
  const [service, setService] = useState<ServiceStatus | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const saveDraft = (complete: boolean) =>
    saveConnectionSettings({
      strategy,
      localUrl,
      remoteUrl: strategy === "local" ? null : remoteUrl,
      onboardingComplete: complete,
    });

  const check = async () => {
    setBusy(true);
    try {
      shutdownRealtimeStores();
      await saveDraft(false);
      const result = await resolveConnection(false, shutdownRealtimeStores);
      setMessage(
        result.healthy
          ? text(`Conexión comprobada: ${result.active_url}`, `Connection verified: ${result.active_url}`)
          : text("Las URL son válidas, pero ningún backend responde.", "The URLs are valid, but no backend responds."),
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const serviceAction = async (action: "status" | "start") => {
    setBusy(true);
    try {
      const status = await controlService("backend", action);
      setService(status);
      setMessage(
        status.load_state === "not-found"
          ? text("El servicio no está instalado. Dax no intentará instalarlo.", "The service is not installed. Dax will not attempt to install it.")
          : `${status.unit}: ${status.active_state} (${status.sub_state})`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    try {
      shutdownRealtimeStores();
      await saveDraft(true);
      await resolveConnection(allowStart, shutdownRealtimeStores);
      onComplete();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const strategyName = strategy === "local"
    ? text("Local", "Local")
    : text("Servidor", "Server");

  return (
    <main className={s.wrap} aria-labelledby="onboarding-title">
      <section className={s.card}>
        <div className={s.progress} aria-label={text("Progreso", "Progress")}>
          {Array.from({ length: ONBOARDING_STEPS }, (_, index) => (
            <span key={index} className={index <= step ? s.progressActive : undefined} />
          ))}
        </div>

        {step === 0 && (
          <div className={s.content}>
            <p className={s.eyebrow}>DAX DESKTOP</p>
            <h1 id="onboarding-title">{text("Tu asistente, tu conexión", "Your assistant, your connection")}</h1>
            <p>{text("Dax usa una sola autoridad: un backend en este equipo o tu servidor. Ahí se procesan y almacenan las conversaciones.", "Dax uses one authority: a backend on this computer or your server. Conversations are processed and stored there.")}</p>
            <div className={s.notice} role="note">
              <strong>{text("Privacidad", "Privacy")}</strong>
              <span>{text("La aplicación no copia tokens entre servidores. Las credenciales se guardan por origen en el keyring del sistema.", "The app never copies tokens between servers. Credentials are stored per origin in the system keyring.")}</span>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className={s.content}>
            <h1 id="onboarding-title">{text("Elige una estrategia", "Choose a strategy")}</h1>
            <div className={s.choices} role="radiogroup" aria-label={text("Estrategia de conexión", "Connection strategy")}>
              {(["local", "remote"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={strategy === value}
                  className={strategy === value ? s.choiceActive : s.choice}
                  onClick={() => {
                    setStrategy(value);
                    if (value === "remote") setAllowStart(false);
                  }}
                >
                  <strong>{value === "local" ? text("Local", "Local") : text("Servidor", "Server")}</strong>
                  <span>{value === "local" ? text("La única autoridad se ejecuta en este equipo", "The sole authority runs on this computer") : text("Tu servidor es la única autoridad; sin fallback", "Your server is the sole authority; no fallback")}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className={s.content}>
            <h1 id="onboarding-title">{text("Configura y comprueba", "Configure and verify")}</h1>
            {strategy === "local" && (
              <label className={s.field}>
                <span>{text("URL local (solo loopback)", "Local URL (loopback only)")}</span>
                <TextInput value={localUrl} spellCheck={false} onChange={(event) => setLocalUrl(event.target.value)} />
              </label>
            )}
            {strategy !== "local" && (
              <label className={s.field}>
                <span>{text("URL del servidor (HTTPS)", "Server URL (HTTPS)")}</span>
                <TextInput value={remoteUrl} spellCheck={false} placeholder="https://dax.example.com" onChange={(event) => setRemoteUrl(event.target.value)} />
              </label>
            )}
            <Button loading={busy} disabled={!canAdvanceOnboarding(step, strategy, localUrl, remoteUrl)} onClick={() => void check()}>{text("Comprobar conexión", "Check connection")}</Button>
            {message && <p className={s.status} role="status">{message}</p>}
          </div>
        )}

        {step === 3 && (
          <div className={s.content}>
            <h1 id="onboarding-title">{text("Servicio local", "Local service")}</h1>
            <p>{text("Si elegiste Local, dax-assistant.service es la autoridad. Esta aplicación solo puede iniciarlo con tu permiso. Las capacidades de este portátil para un servidor remoto pertenecen a un servicio separado dax edge; nunca son un backend de fallback.", "If you chose Local, dax-assistant.service is the authority. This app can start it only with your permission. Laptop capabilities for a remote server belong to a separate dax edge service; they are never a fallback backend.")}</p>
            <div className={s.actions}>
              <Button loading={busy} onClick={() => void serviceAction("status")}>{text("Detectar", "Detect")}</Button>
              <Button
                variant="secondary"
                loading={busy}
                disabled={strategy === "remote" || !service || service.active_state === "active"}
                onClick={() => void serviceAction("start")}
              >
                {text("Iniciar ahora", "Start now")}
              </Button>
            </div>
            <label className={s.consent}>
              <input type="checkbox" checked={allowStart} disabled={strategy === "remote"} onChange={(event) => setAllowStart(event.target.checked)} />
              <span>{text("Permitir iniciar el servicio al guardar si se elige el backend local y está detenido.", "Allow starting the service on save when the local backend is selected and stopped.")}</span>
            </label>
            {(message || service) && <p className={s.status} role="status">{message}</p>}
          </div>
        )}

        {step === 4 && (
          <div className={s.content}>
            <h1 id="onboarding-title">{text("Revisa y guarda", "Review and save")}</h1>
            <dl className={s.summary}>
              <div><dt>{text("Estrategia", "Strategy")}</dt><dd>{strategyName}</dd></div>
               {strategy === "local" && <div><dt>{text("Local", "Local")}</dt><dd>{localUrl}</dd></div>}
              {strategy !== "local" && <div><dt>{text("Servidor", "Server")}</dt><dd>{remoteUrl}</dd></div>}
              <div><dt>{text("Inicio del servicio", "Service start")}</dt><dd>{allowStart ? text("Permitido", "Allowed") : text("No permitido", "Not allowed")}</dd></div>
            </dl>
            {message && <p className={s.status} role="alert">{message}</p>}
          </div>
        )}

        <footer className={s.footer}>
          <Button variant="ghost" disabled={step === 0 || busy} onClick={() => setStep((value) => value - 1)}>{text("Volver", "Back")}</Button>
          {step < ONBOARDING_STEPS - 1 ? (
            <Button variant="primary" disabled={!canAdvanceOnboarding(step, strategy, localUrl, remoteUrl)} onClick={() => setStep((value) => value + 1)}>{text("Continuar", "Continue")}</Button>
          ) : (
            <Button variant="primary" loading={busy} onClick={() => void finish()}>{text("Guardar y continuar", "Save and continue")}</Button>
          )}
        </footer>
      </section>
    </main>
  );
}
