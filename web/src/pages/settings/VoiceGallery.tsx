import { useEffect, useRef, useState } from "react";
import { Play, Radio, Square } from "lucide-react";
import { api } from "../../api/client";
import { useToast } from "../../components/ui";

const KOKORO_VOICES = [
  { id: "em_alex", label: "Alex", detail: "Spanish, masculine" },
  { id: "ef_dora", label: "Dora", detail: "Spanish, feminine" },
];

const OPENAI_VOICES = ["marin", "cedar", "coral", "nova", "sage", "shimmer", "alloy", "ash", "ballad", "echo", "fable", "onyx", "verse"];

export function VoiceGallery({
  kokoroVoice,
  kokoroSpeed,
  openAIVoice,
  openAIModel,
  openAIInstructions,
  openAIConfigured,
  onKokoroVoice,
  onOpenAIVoice,
}: {
  kokoroVoice: string;
  kokoroSpeed: number;
  openAIVoice: string;
  openAIModel: string;
  openAIInstructions: string;
  openAIConfigured: boolean;
  onKokoroVoice: (voice: string) => void;
  onOpenAIVoice: (voice: string) => void;
}) {
  const toast = useToast();
  const [playing, setPlaying] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef("");
  const requestRef = useRef(0);

  useEffect(() => () => {
    requestRef.current += 1;
    audioRef.current?.pause();
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
  }, []);

  const preview = async (engine: "kokoro" | "openai", voice: string) => {
    const request = requestRef.current + 1;
    requestRef.current = request;
    if (playing === `${engine}:${voice}`) {
      audioRef.current?.pause();
      setPlaying("");
      return;
    }
    audioRef.current?.pause();
    setPlaying(`${engine}:${voice}`);
    try {
      const blob = await api.previewVoice({
        engine,
        voice,
        language: "es",
        speed: kokoroSpeed,
        model: openAIModel,
        instructions: openAIInstructions,
      });
      if (request !== requestRef.current) return;
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = URL.createObjectURL(blob);
      const audio = new Audio(urlRef.current);
      audioRef.current = audio;
      audio.onended = () => setPlaying("");
      audio.onerror = () => setPlaying("");
      await audio.play();
    } catch (error) {
      if (request !== requestRef.current) return;
      setPlaying("");
      toast.show(error instanceof Error ? error.message : "Preview failed", "danger");
    }
  };

  const voiceButton = (engine: "kokoro" | "openai", id: string, label: string, detail: string, selected: boolean) => (
    <button
      key={id}
      type="button"
      className={`group flex min-w-0 items-center gap-3 rounded-xl border p-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/50 ${selected ? "border-primary bg-primary/5" : "border-separator bg-background"}`}
      onClick={() => {
        if (engine === "kokoro") onKokoroVoice(id); else onOpenAIVoice(id);
        void preview(engine, id);
      }}
      title={!openAIConfigured && engine === "openai" ? "Save an OpenAI API key before previewing" : undefined}
    >
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${playing === `${engine}:${id}` ? "bg-primary text-primary-foreground" : "bg-content2 text-muted group-hover:text-primary"}`}>
        {playing === `${engine}:${id}` ? <Square size={13} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium capitalize">{label}</span>
        <span className="block truncate text-[11px] text-muted">{detail}</span>
      </span>
    </button>
  );

  return (
    <section className="rounded-2xl border border-separator bg-content1 p-4">
      <div className="mb-4 flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary/10 text-primary"><Radio size={18} /></span>
        <div><p className="text-sm font-semibold">Voice gallery</p><p className="text-xs text-muted">Select and hear a real sample without changing the live assistant.</p></div>
      </div>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">Kokoro local · Apache 2.0 · free</p>
      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        {KOKORO_VOICES.map((voice) => voiceButton("kokoro", voice.id, voice.label, voice.detail, kokoroVoice === voice.id))}
      </div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">OpenAI hosted · paid · proprietary</p>
        {!openAIConfigured && <span className="text-[11px] text-warning">API key required</span>}
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {OPENAI_VOICES.map((voice) => voiceButton("openai", voice, voice, "Multilingual hosted voice", openAIVoice === voice))}
      </div>
    </section>
  );
}
