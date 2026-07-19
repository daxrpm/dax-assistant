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
  const toast = useToast();
  const [enrolled, setEnrolled] = useState<boolean | null>(null);
  const [samples, setSamples] = useState<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [modelMissing, setModelMissing] = useState(false);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

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
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      void audioCtxRef.current?.close();
    },
    [],
  );

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
        const raw = new Blob(chunksRef.current, { type: "audio/webm" });
        void toEnrollmentWav(raw)
          .then((wav) => setSamples((prev) => [...prev, wav]))
          .catch(() => toast.show("Could not process that recording", "danger"));
      };
      recorder.start();
      setRecording(true);
    } catch {
      toast.show("Microphone permission denied", "danger");
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
      toast.show("Voice profile enrolled", "success");
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setModelMissing(true);
        toast.show("Voice ID model is not available on the server", "danger");
      } else if (err instanceof ApiError && err.status === 422) {
        toast.show(err.message || "Samples were unusable — re-record them", "danger");
      } else {
        toast.show(err instanceof Error ? err.message : "Enrollment failed", "danger");
      }
    } finally {
      setUploading(false);
    }
  };

  const removeProfile = async () => {
    try {
      await api.deleteVoiceProfile();
      setEnrolled(false);
      toast.show("Voice profile deleted", "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Delete failed", "danger");
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Voice ID enrollment"
        subtitle={`Record ${MIN_SAMPLES}–${MAX_SAMPLES} samples so the assistant recognizes you`}
        actions={
          enrolled === null ? null : enrolled ? (
            <div className={p.actions}>
              <Badge tone="success" dot>
                Enrolled
              </Badge>
              <Button size="sm" variant="ghost" onClick={() => void removeProfile()}>
                Delete profile
              </Button>
            </div>
          ) : (
            <Badge tone="neutral">Not enrolled</Badge>
          )
        }
      />
      <PanelBody>
        <div className={p.rows}>
          {modelMissing && (
            <div className={p.notice}>
              <span className={p.noticeIcon}>
                <AlertIcon size={14} />
              </span>
              <span>
                The server does not have the Voice ID model installed, so enrollment
                cannot run. Install the <code>voice</code> extra on the backend and try
                again.
              </span>
            </div>
          )}

          <div className={s.recorder}>
            <Button
              variant={recording ? "destructive" : "secondary"}
              onClick={() => (recording ? stopRecording() : void startRecording())}
              disabled={samples.length >= MAX_SAMPLES && !recording}
            >
              {recording ? (
                <>
                  <VoiceIcon size={14} />
                  Stop
                </>
              ) : (
                <>
                  <PlayIcon size={14} />
                  Record sample
                </>
              )}
            </Button>

            <div className={s.meterTrack}>
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
                  <span>Sample {i + 1}</span>
                  <span className={p.dim}>{(sample.size / 1024).toFixed(0)} KB</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      setSamples((prev) => prev.filter((_, idx) => idx !== i))
                    }
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
              Enroll {samples.length} sample{samples.length !== 1 ? "s" : ""}
            </Button>
          </div>

          <p className={p.hint}>
            Speak naturally for a few seconds per sample, in the room you normally use.
            Fewer than {MIN_SAMPLES} samples is rejected by the server.
          </p>
        </div>
      </PanelBody>
    </Panel>
  );
}
