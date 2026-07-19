import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../../api/client";
import { AlertIcon, PlayIcon, TrashIcon, VoiceIcon } from "../../components/icons";
import {
  Badge,
  Button,
  Panel,
  PanelBody,
  PanelHeader,
  useToast,
} from "../../design/primitives";
import { toEnrollmentWav } from "../../lib/audio";
import p from "../page.module.css";
import s from "./VoiceEnrollment.module.css";
import { useI18n } from "../../i18n/I18n";

const MIN_SAMPLES = 3;
const MAX_SAMPLES = 5;

/**
 * Speaker-ID enrollment.
 *
 * Records 3–5 samples in-app, transcodes each to 16 kHz WAV and uploads them as
 * multipart. The server enforces the same bounds and answers 422 for unusable
 * speech or a bad count, 503 when the Voice ID model is not installed — those
 * are surfaced separately because the remedies are completely different.
 */
export function VoiceEnrollment() {
  const { text } = useI18n();
  const toast = useToast();
  const [enrolled, setEnrolled] = useState<boolean | null>(null);
  const [samples, setSamples] = useState<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [level, setLevel] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [modelMissing, setModelMissing] = useState(false);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const generationRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    api
      .voiceProfile()
      .then((profile) => setEnrolled(profile.enrolled))
      .catch(() => setEnrolled(null));
  }, []);

  // Stop everything if the tab unmounts mid-recording — a live mic stream that
  // outlives the screen keeps the OS recording indicator on.
  useEffect(
    () => () => {
      mountedRef.current = false;
      generationRef.current += 1;
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      void audioCtxRef.current?.close();
    },
    [],
  );

  const startRecording = async () => {
    const generation = ++generationRef.current;
    setRequesting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current || generation !== generationRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;

      // Native-mic level meter during capture (PLAN.md 6.2 desktop advantage).
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let peak = 0;
        for (const value of data) peak = Math.max(peak, Math.abs(value - 128) / 128);
        setLevel(peak);
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = () => {
        if (!mountedRef.current || generation !== generationRef.current) return;
        const raw = new Blob(chunksRef.current, { type: "audio/webm" });
        void toEnrollmentWav(raw)
          .then((wav) => {
            if (mountedRef.current && generation === generationRef.current) {
              setSamples((prev) => [...prev, wav]);
            }
          })
          .catch(() => {
            if (mountedRef.current && generation === generationRef.current) {
              toast.show(text("No se pudo procesar la grabación", "Could not process that recording"), "danger");
            }
          });
      };
      recorder.start();
      setRecording(true);
    } catch {
      if (mountedRef.current && generation === generationRef.current) {
        toast.show(text("Permiso de micrófono denegado", "Microphone permission denied"), "danger");
      }
    } finally {
      if (mountedRef.current && generation === generationRef.current) setRequesting(false);
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    void audioCtxRef.current?.close();
    audioCtxRef.current = null;
    setLevel(0);
    setRecording(false);
  };

  const upload = async () => {
    setUploading(true);
    setModelMissing(false);
    try {
      const result = await api.enrollVoice(samples);
      setEnrolled(result.enrolled);
      setSamples([]);
      toast.show(text("Perfil de voz registrado", "Voice profile enrolled"), "success");
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setModelMissing(true);
        toast.show(text("El modelo de identificación de voz no está disponible en el servidor", "Voice ID model is not available on the server"), "danger");
      } else if (err instanceof ApiError && err.status === 422) {
        toast.show(err.message || text("Las muestras no se pudieron usar; vuelve a grabarlas", "Samples were unusable — re-record them"), "danger");
      } else {
        toast.show(err instanceof Error ? err.message : text("Falló el registro", "Enrollment failed"), "danger");
      }
    } finally {
      setUploading(false);
    }
  };

  const removeProfile = async () => {
    try {
      await api.deleteVoiceProfile();
      setEnrolled(false);
      toast.show(text("Perfil de voz eliminado", "Voice profile deleted"), "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : text("No se pudo eliminar", "Delete failed"), "danger");
    }
  };

  return (
    <Panel>
      <PanelHeader
        title={text("Registro de identificación de voz", "Voice ID enrollment")}
        subtitle={text(`Graba ${MIN_SAMPLES}–${MAX_SAMPLES} muestras para que el asistente te reconozca`, `Record ${MIN_SAMPLES}–${MAX_SAMPLES} samples so the assistant recognizes you`)}
        actions={
          enrolled === null ? null : enrolled ? (
            <div className={p.actions}>
              <Badge tone="success" dot>
                 {text("Registrado", "Enrolled")}
              </Badge>
              <Button size="sm" variant="ghost" onClick={() => void removeProfile()}>
                 {text("Eliminar perfil", "Delete profile")}
              </Button>
            </div>
          ) : (
             <Badge tone="neutral">{text("Sin registrar", "Not enrolled")}</Badge>
          )
        }
      />
      <PanelBody>
        <div className={p.rows}>
          {modelMissing && (
            <div className={p.notice} role="alert">
              <span className={p.noticeIcon}>
                <AlertIcon size={14} />
              </span>
              <span>
                 {text("El servidor no tiene instalado el modelo Voice ID. Instala el extra ", "The server does not have the Voice ID model installed. Install the ")}<code>voice</code>{text(" en el backend y vuelve a intentarlo.", " extra on the backend and try again.")}
              </span>
            </div>
          )}

          <div className={s.recorder}>
            <Button
              variant={recording ? "destructive" : "secondary"}
              onClick={() => (recording ? stopRecording() : void startRecording())}
              disabled={requesting || (samples.length >= MAX_SAMPLES && !recording)}
              aria-pressed={recording}
            >
              {recording ? (
                <>
                  <VoiceIcon size={14} />
                   {text("Detener", "Stop")}
                </>
              ) : (
                <>
                  <PlayIcon size={14} />
                   {text("Grabar muestra", "Record sample")}
                </>
              )}
            </Button>

            <div
              className={s.meterTrack}
              role="progressbar"
              aria-label={text("Nivel del micrófono", "Microphone level")}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(Math.min(100, level * 140))}
            >
              <div
                className={s.meterFill}
                style={{ width: `${Math.min(100, level * 140)}%` }}
              />
            </div>

            <span className={p.dim}>
              {samples.length} / {MAX_SAMPLES}
            </span>
          </div>

          {samples.length > 0 && (
            <div className={s.sampleList}>
              {samples.map((sample, i) => (
                <div key={i} className={s.sample}>
                   <span>{text("Muestra", "Sample")} {i + 1}</span>
                  <span className={p.dim}>{(sample.size / 1024).toFixed(0)} KB</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      setSamples((prev) => prev.filter((_, idx) => idx !== i))
                    }
                    aria-label={text(`Eliminar muestra ${i + 1}`, `Delete sample ${i + 1}`)}
                  >
                    <TrashIcon size={12} />
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className={p.actionsEnd}>
            <Button
              variant="primary"
              loading={uploading}
              disabled={samples.length < MIN_SAMPLES || uploading}
              onClick={() => void upload()}
            >
               {text(`Registrar ${samples.length} muestra(s)`, `Enroll ${samples.length} sample(s)`)}
            </Button>
          </div>

          <p className={p.hint}>
             {text(`Habla con naturalidad unos segundos por muestra, en la habitación habitual. El servidor rechaza menos de ${MIN_SAMPLES} muestras.`, `Speak naturally for a few seconds per sample, in the room you normally use. Fewer than ${MIN_SAMPLES} samples is rejected by the server.`)}
          </p>
        </div>
      </PanelBody>
    </Panel>
  );
}
