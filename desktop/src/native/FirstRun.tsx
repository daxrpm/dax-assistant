import { useCallback, useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "../api/client";
import { Button, TextInput } from "../design/primitives";
import { useI18n } from "../i18n/I18n";
import { isTauriRuntime } from "./environment";
import {
  enrollCapabilityNode,
  getCapabilityNodeStatus,
  type CapabilityNodeEnrollmentStatus,
} from "./capabilityNode";
import { controlService, type ServiceStatus } from "./service";
import s from "./FirstRun.module.css";

const SETUP_KEY = "dax.setup.complete";

export const FIRST_RUN_STEPS = 4;

/** Providers worth offering on a first run, in the order they are offered. */
export const FIRST_RUN_PROVIDERS = ["openai", "anthropic", "deepseek", "ollama"] as const;
export type FirstRunProvider = (typeof FIRST_RUN_PROVIDERS)[number];

/** Ollama is local, so it is the one option that needs no key to be usable. */
export function providerNeedsKey(provider: FirstRunProvider): boolean {
  return provider !== "ollama";
}

export function canAdvanceFirstRun(
  step: number,
  provider: FirstRunProvider,
  key: string,
  saved: boolean,
): boolean {
  if (step !== 0) return true;
  return saved || !providerNeedsKey(provider) || key.trim().length > 0;
}

export function isFirstRunComplete(): boolean {
  try {
    return localStorage.getItem(SETUP_KEY) === "1";
  } catch {
    // Private mode or a locked-down profile. Treat it as done rather than
    // trapping the user in a wizard they cannot dismiss.
    return true;
  }
}

export function markFirstRunComplete(): void {
  try {
    localStorage.setItem(SETUP_KEY, "1");
  } catch {
    // Nothing to do: the flow is re-openable from settings either way.
  }
}

export function resetFirstRun(): void {
  try {
    localStorage.removeItem(SETUP_KEY);
  } catch {
    // As above.
  }
}

/**
 * The half of setup that needs a session.
 *
 * Connection strategy is settled before login, in `Onboarding` — it has to be,
 * since there is nothing to log into until it is. Everything here is the
 * opposite: choosing a model, enrolling this laptop, and inviting a phone all
 * speak to an authenticated backend, so they cannot run any earlier.
 *
 * Every step is skippable and the whole flow is re-openable from settings. A
 * first run that traps someone behind a decision they are not ready to make is
 * worse than no first run at all.
 */
export function FirstRun({ onDone }: { onDone: () => void }) {
  const { text } = useI18n();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const [provider, setProvider] = useState<FirstRunProvider>("openai");
  const [apiKey, setApiKey] = useState("");
  const [modelSaved, setModelSaved] = useState(false);

  const [nodeCommand, setNodeCommand] = useState("");
  const [nodeName, setNodeName] = useState("");
  const [nodeEnrollment, setNodeEnrollment] = useState<CapabilityNodeEnrollmentStatus | null>(null);
  const [nodeService, setNodeService] = useState<ServiceStatus | null>(null);
  const [enableNodeService, setEnableNodeService] = useState(false);
  const [pairing, setPairing] = useState<{ uri: string; code: string } | null>(null);
  const [remaining, setRemaining] = useState(0);

  // The pairing code is short-lived by design, so the UI has to say so rather
  // than leaving a dead QR on screen.
  useEffect(() => {
    if (remaining <= 0) return;
    const timer = setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => clearInterval(timer);
  }, [remaining]);

  useEffect(() => {
    if (remaining === 0) setPairing(null);
  }, [remaining]);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    void Promise.all([
      getCapabilityNodeStatus().catch(() => null),
      controlService("capability_node", "status").catch(() => null),
    ]).then(([enrollment, service]) => {
      setNodeEnrollment(enrollment);
      setNodeService(service);
      if (enrollment?.node_name) setNodeName(enrollment.node_name);
    });
  }, []);

  const saveModel = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const body: Record<string, unknown> = { default_provider: provider };
      if (providerNeedsKey(provider) && apiKey.trim()) {
        body[`${provider}_api_key`] = apiKey.trim();
      }
      await api.updateLLM(body);
      setModelSaved(true);
      setApiKey("");
      setMessage(text("Modelo guardado.", "Model saved."));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }, [apiKey, provider, text]);

  const enrolNode = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const response = await api.pairDevice("capability_node");
      if (isTauriRuntime()) {
        const enrollment = await enrollCapabilityNode(response.code, nodeName);
        setNodeEnrollment(enrollment);
        if (enableNodeService) {
          setNodeService(await controlService("capability_node", "enable_now"));
        } else {
          setNodeService(await controlService("capability_node", "status").catch(() => null));
        }
        setMessage(
          enableNodeService
            ? text("Nodo inscrito y servicio habilitado.", "Node enrolled and service enabled.")
            : text("Nodo inscrito. El servicio no se ha iniciado.", "Node enrolled. The service was not started."),
        );
      } else {
        setNodeCommand(
          `dax edge enroll --server ${response.backend_url} --code ${response.code} --name <name>`,
        );
        setRemaining(response.expires_in_seconds);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }, [enableNodeService, nodeName, text]);

  const pairPhone = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const response = await api.pairDevice("client");
      setPairing({ uri: response.pairing_uri, code: response.code });
      setRemaining(response.expires_in_seconds);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }, []);

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setMessage(text("Copiado.", "Copied."));
    } catch {
      setMessage(text("No se pudo copiar.", "Could not copy."));
    }
  };

  const finish = () => {
    markFirstRunComplete();
    onDone();
  };

  return (
    <main className={s.wrap} aria-labelledby="first-run-title">
      <section className={s.card}>
        <div className={s.progress} aria-label={text("Progreso", "Progress")}>
          {Array.from({ length: FIRST_RUN_STEPS }, (_, index) => (
            <span key={index} className={index <= step ? s.progressActive : undefined} />
          ))}
        </div>

        {step === 0 && (
          <div className={s.content}>
            <p className={s.eyebrow}>{text("PASO 1 DE 3", "STEP 1 OF 3")}</p>
            <h1 id="first-run-title">{text("Elige un modelo", "Choose a model")}</h1>
            <p>
              {text(
                "Puedes cambiarlo cuando quieras en Ajustes → Inteligencia. La clave se guarda cifrada en tu backend, nunca en esta aplicación.",
                "You can change this any time in Settings → Intelligence. The key is stored encrypted on your backend, never in this app.",
              )}
            </p>
            <div
              className={s.choices}
              role="radiogroup"
              aria-label={text("Proveedor", "Provider")}
            >
              {FIRST_RUN_PROVIDERS.map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={provider === value}
                  className={provider === value ? s.choiceActive : s.choice}
                  onClick={() => {
                    setProvider(value);
                    setModelSaved(false);
                  }}
                >
                  <strong>{value}</strong>
                  <span>
                    {value === "ollama"
                      ? text("Local, sin clave", "Local, no key")
                      : text("Requiere clave API", "Needs an API key")}
                  </span>
                </button>
              ))}
            </div>
            {providerNeedsKey(provider) && (
              <label className={s.field}>
                <span>{text("Clave API", "API key")}</span>
                <TextInput
                  type="password"
                  value={apiKey}
                  spellCheck={false}
                  autoComplete="off"
                  placeholder={modelSaved ? text("Ya guardada", "Already saved") : "sk-…"}
                  onChange={(event) => setApiKey(event.target.value)}
                />
              </label>
            )}
            <Button
              loading={busy}
              disabled={!canAdvanceFirstRun(0, provider, apiKey, modelSaved)}
              onClick={() => void saveModel()}
            >
              {text("Guardar modelo", "Save model")}
            </Button>
          </div>
        )}

        {step === 1 && (
          <div className={s.content}>
            <p className={s.eyebrow}>{text("PASO 2 DE 3", "STEP 2 OF 3")}</p>
            <h1 id="first-run-title">{text("Este portátil como nodo", "This laptop as a node")}</h1>
            <p>
              {text(
                "Un nodo presta sus herramientas al asistente y, si lo permites, ejecuta el turno aquí. El historial sigue viviendo en el backend.",
                "A node lends its tools to the assistant and, if you allow it, runs the turn here. History still lives on the backend.",
              )}
            </p>
            {isTauriRuntime() && (
              <>
                <label className={s.field}>
                  <span>{text("Nombre del nodo", "Node name")}</span>
                  <TextInput
                    value={nodeName}
                    maxLength={64}
                    autoComplete="off"
                    placeholder={text("portátil de trabajo", "work laptop")}
                    onChange={(event) => setNodeName(event.target.value)}
                  />
                </label>
                <label className={s.consent}>
                  <input
                    type="checkbox"
                    checked={enableNodeService}
                    onChange={(event) => setEnableNodeService(event.target.checked)}
                  />
                  <span>
                    {text(
                      "Habilitar e iniciar dax-assistant-node.service después de inscribir este equipo.",
                      "Enable and start dax-assistant-node.service after enrolling this machine.",
                    )}
                  </span>
                </label>
              </>
            )}
            <Button
              loading={busy}
              disabled={isTauriRuntime() && (!nodeName.trim() || nodeEnrollment?.enrolled === true)}
              onClick={() => void enrolNode()}
            >
              {isTauriRuntime()
                ? text("Inscribir este portátil", "Enroll this laptop")
                : text("Generar comando de inscripción", "Generate enrolment command")}
            </Button>
            {isTauriRuntime() && nodeEnrollment?.enrolled && (
              <p className={s.hint}>
                {text("Inscrito como", "Enrolled as")} <strong>{nodeEnrollment.node_name}</strong>
                {nodeService
                  ? ` · dax-assistant-node.service: ${nodeService.active_state}, ${nodeService.unit_file_state}`
                  : ` · ${text("estado del servicio no disponible", "service status unavailable")}`}
              </p>
            )}
            {nodeCommand && (
              <>
                <div className={s.commandRow}>
                  <code className={s.command}>{nodeCommand}</code>
                  <Button variant="secondary" onClick={() => void copy(nodeCommand)}>
                    {text("Copiar", "Copy")}
                  </Button>
                </div>
                <p className={s.hint}>
                  {text(
                    `Ejecútalo en una terminal de este equipo. El código caduca en ${remaining} s.`,
                    `Run it in a terminal on this machine. The code expires in ${remaining}s.`,
                  )}
                </p>
              </>
            )}
          </div>
        )}

        {step === 2 && (
          <div className={s.content}>
            <p className={s.eyebrow}>{text("PASO 3 DE 3", "STEP 3 OF 3")}</p>
            <h1 id="first-run-title">{text("Vincula tu teléfono", "Pair your phone")}</h1>
            <p>
              {text(
                "Escanea el código desde la app de Dax en Android. El teléfono nunca aprende tu contraseña: canjea este código una vez por su propia credencial.",
                "Scan this from the Dax app on Android. The phone never learns your password: it redeems this code once for its own credential.",
              )}
            </p>
            <Button loading={busy} onClick={() => void pairPhone()}>
              {text("Generar código", "Generate code")}
            </Button>
            {pairing && (
              <div className={s.pairing}>
                <div className={s.qr}>
                  <QRCodeSVG
                    value={pairing.uri}
                    size={148}
                    level="M"
                    marginSize={1}
                    bgColor="#ffffff"
                    fgColor="#0a0f18"
                  />
                </div>
                <div className={s.pairingBody}>
                  <span className={s.code}>{pairing.code.split("").join(" ")}</span>
                  <p className={s.hint}>
                    {text(`Caduca en ${remaining} s.`, `Expires in ${remaining}s.`)}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className={s.content}>
            <p className={s.eyebrow}>{text("LISTO", "DONE")}</p>
            <h1 id="first-run-title">{text("Todo preparado", "You are set up")}</h1>
            <dl className={s.summary}>
              <div>
                <dt>{text("Modelo", "Model")}</dt>
                <dd>{modelSaved ? provider : text("Sin configurar", "Not configured")}</dd>
              </div>
              <div>
                <dt>{text("Nodo", "Node")}</dt>
                <dd>
                  {nodeEnrollment?.enrolled
                    ? text("Inscrito localmente", "Enrolled locally")
                    : nodeCommand
                      ? text("Comando generado", "Command generated")
                    : text("Omitido", "Skipped")}
                </dd>
              </div>
              <div>
                <dt>{text("Teléfono", "Phone")}</dt>
                <dd>
                  {pairing ? text("Código generado", "Code generated") : text("Omitido", "Skipped")}
                </dd>
              </div>
            </dl>
            <p className={s.hint}>
              {text(
                "Puedes retomar cualquiera de estos pasos en Ajustes.",
                "You can pick any of these up again in Settings.",
              )}
            </p>
          </div>
        )}

        {message && (
          <p className={s.status} role="status">
            {message}
          </p>
        )}

        <footer className={s.footer}>
          <Button variant="ghost" disabled={step === 0 || busy} onClick={() => setStep((v) => v - 1)}>
            {text("Volver", "Back")}
          </Button>
          <div className={s.footerRight}>
            <Button variant="ghost" onClick={finish}>
              {text("Omitir configuración", "Skip setup")}
            </Button>
            {step < FIRST_RUN_STEPS - 1 ? (
              <Button variant="primary" onClick={() => setStep((v) => v + 1)}>
                {text("Continuar", "Continue")}
              </Button>
            ) : (
              <Button variant="primary" onClick={finish}>
                {text("Empezar", "Get started")}
              </Button>
            )}
          </div>
        </footer>
      </section>
    </main>
  );
}
