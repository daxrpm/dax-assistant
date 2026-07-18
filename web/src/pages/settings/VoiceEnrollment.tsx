import { useEffect, useRef, useState } from "react";
import { Button } from "@heroui/react";
import { Check, Mic, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "../../api/client";
import { toEnrollmentWav } from "../../lib/audio";
import { useToast } from "../../components/ui";

const PHRASES = [
  "Hola Dax, ¿qué tengo pendiente para hoy?",
  "Pon música tranquila en la sala, por favor.",
  "Recuérdame llamar a casa mañana por la tarde.",
  "Dax, dime el tiempo y abre mi calendario.",
];

export function VoiceEnrollment({
  enrolled,
  onChanged,
}: {
  enrolled: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [recordings, setRecordings] = useState<(Blob | null)[]>(PHRASES.map(() => null));
  const [active, setActive] = useState<number | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [levels, setLevels] = useState<number[]>(Array(24).fill(8));
  const [busy, setBusy] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const frameRef = useRef(0);
  const timeoutRef = useRef(0);
  const intervalRef = useRef(0);

  const cleanupCapture = () => {
    window.clearTimeout(timeoutRef.current);
    window.clearInterval(intervalRef.current);
    cancelAnimationFrame(frameRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void contextRef.current?.close();
    contextRef.current = null;
  };

  useEffect(() => cleanupCapture, []);

  const record = async (index: number) => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      toast.show("This browser cannot record microphone audio", "danger");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;
      setActive(index);
      setCountdown(3);
      let remaining = 3;
      intervalRef.current = window.setInterval(() => {
        remaining -= 1;
        setCountdown(remaining);
        if (remaining === 0) {
          window.clearInterval(intervalRef.current);
          startRecorder(index, stream);
        }
      }, 1000);
    } catch (error) {
      cleanupCapture();
      setActive(null);
      toast.show(error instanceof Error ? error.message : "Microphone permission failed", "danger");
    }
  };

  const startRecorder = (index: number, stream: MediaStream) => {
    const chunks: Blob[] = [];
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data);
    };
    recorder.onstop = async () => {
      try {
        const wav = await toEnrollmentWav(new Blob(chunks, { type: recorder.mimeType }));
        setRecordings((current) => current.map((item, itemIndex) => itemIndex === index ? wav : item));
      } catch (error) {
        toast.show(error instanceof Error ? error.message : "Could not process recording", "danger");
      } finally {
        cleanupCapture();
        setActive(null);
        setLevels(Array(24).fill(8));
      }
    };
    recorder.start(200);
    visualize(stream);
    timeoutRef.current = window.setTimeout(() => recorder.stop(), 5200);
  };

  const visualize = (stream: MediaStream) => {
    const context = new AudioContext();
    contextRef.current = context;
    const analyser = context.createAnalyser();
    analyser.fftSize = 64;
    context.createMediaStreamSource(stream).connect(analyser);
    const values = new Uint8Array(analyser.frequencyBinCount);
    const draw = () => {
      analyser.getByteFrequencyData(values);
      setLevels(Array.from(values.slice(0, 24), (value) => Math.max(8, Math.round(value / 2.7))));
      frameRef.current = requestAnimationFrame(draw);
    };
    draw();
  };

  const submit = async () => {
    const complete = recordings.filter((sample): sample is Blob => sample !== null);
    if (complete.length < 3) return;
    setBusy(true);
    try {
      await api.enrollVoice(complete);
      toast.show("Voice ID profile enrolled", "success");
      onChanged();
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Enrollment failed", "danger");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.deleteVoiceProfile();
      setRecordings(PHRASES.map(() => null));
      toast.show("Voice ID profile removed", "success");
      onChanged();
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Could not remove profile", "danger");
    } finally {
      setBusy(false);
    }
  };

  const completeCount = recordings.filter(Boolean).length;
  return (
    <section className="overflow-hidden rounded-2xl border border-separator bg-background">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-separator bg-gradient-to-r from-primary/10 to-transparent p-4">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/15 text-primary"><ShieldCheck size={20} /></span>
          <div>
            <p className="text-sm font-semibold">Voice ID studio</p>
            <p className="text-xs text-muted">Four short samples make recognition safer and more reliable.</p>
          </div>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${enrolled ? "bg-success/15 text-success" : "bg-warning/15 text-warning"}`}>
          {enrolled ? "Profile active" : `${completeCount}/4 captured`}
        </span>
      </div>
      <div className="grid gap-2 p-4 md:grid-cols-2">
        {PHRASES.map((phrase, index) => {
          const isActive = active === index;
          const done = recordings[index] !== null;
          return (
            <div key={phrase} className={`rounded-xl border p-3 transition-colors ${isActive ? "border-primary bg-primary/5" : "border-separator"}`}>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">Sample {index + 1}</span>
                {done && <Check size={15} className="text-success" />}
              </div>
              <p className="min-h-10 text-sm leading-5">“{phrase}”</p>
              {isActive && (
                <div className="my-3 flex h-14 items-center justify-center gap-1 rounded-lg bg-content2 px-3">
                  {countdown > 0 ? <span className="text-2xl font-semibold text-primary">{countdown}</span> : levels.map((level, levelIndex) => (
                    <span key={levelIndex} className="w-1 rounded-full bg-primary transition-[height]" style={{ height: `${level}%` }} />
                  ))}
                </div>
              )}
              <Button size="sm" variant={done ? "secondary" : "tertiary"} isDisabled={active !== null || busy} onPress={() => record(index)}>
                {done ? <RotateCcw size={14} /> : <Mic size={14} />}
                {done ? "Record again" : "Record 5 seconds"}
              </Button>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap justify-end gap-2 border-t border-separator p-4">
        {enrolled && <Button size="sm" variant="tertiary" isDisabled={busy || active !== null} onPress={remove}><Trash2 size={14} />Remove profile</Button>}
        <Button size="sm" variant="primary" isDisabled={completeCount < 3 || busy || active !== null} onPress={submit}>
          <ShieldCheck size={14} />{busy ? "Building profile..." : enrolled ? "Replace profile" : "Enroll my voice"}
        </Button>
      </div>
    </section>
  );
}
