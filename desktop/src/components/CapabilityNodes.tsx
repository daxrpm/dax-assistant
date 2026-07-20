import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { CapabilityNode, NodePolicy } from "../api/types";
import { useI18n } from "../i18n/I18n";
import s from "./CapabilityNodes.module.css";

/**
 * Per-node policy, listed with live presence.
 *
 * The LED is the point of the component. A policy whose effect you cannot see
 * is a policy nobody trusts, so every row says whether that laptop is actually
 * up right now — taken from the hub's open socket, not from the last time the
 * node asked for a token.
 */
export function CapabilityNodes() {
  const { locale, t } = useI18n();
  const text = useCallback(
    (es: string, en: string) => (locale === "es" ? es : en),
    [locale],
  );

  const [nodes, setNodes] = useState<CapabilityNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const fleet = await api.nodes();
      setNodes(fleet.nodes);
      setError(null);
    } catch {
      setNodes([]);
      setError(text("No se pudo leer la lista de nodos.", "Could not read the node list."));
    }
  }, [text]);

  useEffect(() => {
    void load();
    // Presence changes without us doing anything, so the list would otherwise
    // go stale the moment the laptop sleeps.
    const timer = setInterval(() => void load(), 10_000);
    return () => clearInterval(timer);
  }, [load]);

  const update = async (id: string, patch: Partial<NodePolicy>) => {
    setBusy(id);
    // Optimistic: the switch has to feel like a switch. A failure reloads the
    // truth from the backend rather than leaving the row lying.
    setNodes((prev) =>
      prev?.map((n) => (n.id === id ? { ...n, policy: { ...n.policy, ...patch } } : n)) ?? prev,
    );
    try {
      await api.updateNodePolicy(id, patch);
      setError(null);
    } catch {
      setError(text("No se pudo guardar la política.", "Could not save the policy."));
      await load();
    } finally {
      setBusy(null);
    }
  };

  if (nodes === null) return <p className={s.empty}>{t("common.loading")}</p>;

  if (nodes.length === 0) {
    return (
      <p className={s.empty}>
        {text(
          "Ningún portátil inscrito todavía. Se inscriben desde Acceso → Dispositivos.",
          "No laptop enrolled yet. Enrol one from Access → Devices.",
        )}
      </p>
    );
  }

  return (
    <>
      {error && <p className={s.error}>{error}</p>}
      <ul className={s.list}>
        {nodes.map((node) => (
          <li key={node.id} className={s.item}>
            <div className={s.head}>
              <span
                className={`${s.led} ${node.connected && !node.revoked ? s.ledLive : s.ledOff}`}
                aria-hidden="true"
              />
              <span className={s.headBody}>
                <span className={s.name}>{node.name}</span>
                <span className={s.meta}>
                  {node.platform}
                  {" · "}
                  {node.revoked
                    ? text("revocado", "revoked")
                    : node.connected
                      ? text("conectado", "connected")
                      : text("apagado", "off")}
                </span>
              </span>
            </div>

            <div className={s.controls}>
              <label className={s.control}>
                <input
                  type="checkbox"
                  checked={node.policy.process_locally}
                  disabled={busy === node.id || node.revoked}
                  onChange={(e) => void update(node.id, { process_locally: e.target.checked })}
                />
                <span className={s.controlBody}>
                  <span className={s.controlLabel}>
                    {text("Procesar aquí", "Process here")}
                  </span>
                  <span className={s.controlHelp}>
                    {text(
                      "Ejecuta el turno en este portátil. Apagado, solo presta sus herramientas.",
                      "Runs the turn on this laptop. Off, it only lends its tools.",
                    )}
                  </span>
                </span>
              </label>

              <label className={s.control}>
                <span className={s.controlBody}>
                  <span className={s.controlLabel}>{text("Inferencia", "Inference")}</span>
                  <span className={s.controlHelp}>
                    {text(
                      "«Auto» fija el modelo al portátil solo si es local (Ollama). Un proveedor en la nube lo llama quien tenga la conversación: enrutarlo por el portátil añade un salto y no quita ninguno.",
                      "“Auto” pins the model to the laptop only when it is local (Ollama). A cloud provider is called by whoever holds the conversation: routing it through the laptop adds a hop and removes none.",
                    )}
                  </span>
                </span>
                <select
                  className={s.select}
                  value={node.policy.inference}
                  disabled={busy === node.id || node.revoked}
                  onChange={(e) =>
                    void update(node.id, { inference: e.target.value as NodePolicy["inference"] })
                  }
                >
                  <option value="auto">{text("Auto (recomendado)", "Auto (recommended)")}</option>
                  <option value="local">{text("Siempre el portátil", "Always the laptop")}</option>
                  <option value="server">{text("Siempre el backend", "Always the backend")}</option>
                </select>
              </label>

              <label className={s.control}>
                <span className={s.controlBody}>
                  <span className={s.controlLabel}>{text("Voz", "Speech")}</span>
                  <span className={s.controlHelp}>
                    {text(
                      "Transcripción y síntesis junto al micrófono. Es la ganancia real de latencia: el audio pesa.",
                      "Transcription and synthesis next to the microphone. This is the real latency win: audio is bulky.",
                    )}
                  </span>
                </span>
                <select
                  className={s.select}
                  value={node.policy.voice}
                  disabled={busy === node.id || node.revoked}
                  onChange={(e) =>
                    void update(node.id, { voice: e.target.value as NodePolicy["voice"] })
                  }
                >
                  <option value="auto">{text("Auto (recomendado)", "Auto (recommended)")}</option>
                  <option value="local">{text("Siempre el portátil", "Always the laptop")}</option>
                  <option value="server">{text("Siempre el backend", "Always the backend")}</option>
                </select>
              </label>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
