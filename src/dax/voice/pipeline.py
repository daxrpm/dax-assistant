"""Voice pipeline — wake word, listen, transcribe, respond.

Runs in a dedicated thread because audio I/O is blocking. Communicates
with the async orchestrator via the message bus (inbound) and receives
routed responses from the dispatcher through the voice channel's
response queue.

State machine::

    IDLE ──(wake word)──► LISTENING ──(silence)──► PROCESSING
      ▲                                                │
      │          CONVERSING ◄───── SPEAKING ◄──────────┘
      │              │
      │         (user replies → LISTENING)
      │              │
      └──(timeout)───┘

CONVERSING is the key addition: after speaking, Dax keeps listening
for follow-up speech WITHOUT requiring the wake word again. This enables
natural multi-turn conversations like Alexa's "follow-up mode".
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
import uuid
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from dax.core.exceptions import STTError, TTSError, VoiceError
from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.voice.audio_io import CHUNK_SIZE, SAMPLE_RATE, AudioCapture, AudioPlayer
from dax.voice.speaker import SpeakerVerifier
from dax.voice.stt import SpeechToText
from dax.voice.tts import build_tts
from dax.voice.vad import VAD_CHUNK_SIZE, VoiceActivityDetector
from dax.voice.wakeword import WakeWordDetector

if TYPE_CHECKING:
    from dax.channels.voice_channel import VoiceChannel
    from dax.core.config import VoiceConfig
    from dax.orchestrator.approval import ApprovalManager
    from dax.orchestrator.bus import MessageBus

logger = logging.getLogger(__name__)

# Safety limits
_MAX_RECORDING_SECONDS = 30


# Split assistant text into sentence-ish chunks for incremental TTS playback.
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]*")


def _clean_for_speech(text: str) -> str:
    """Strip markdown so the TTS doesn't read symbols like '**' aloud.

    Belt-and-suspenders alongside the voice system prompt: even if the model
    emits markdown, the synthesizer should speak clean prose.
    """
    # Links/images: [label](url) -> label, ![alt](url) -> alt
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Inline emphasis / code markers
    text = re.sub(r"(\*\*|\*|__|_|`|~~)", "", text)
    # Line-start markers: headings, quotes, bullets, numbered lists
    text = re.sub(r"(?m)^\s{0,3}(#{1,6}\s+|>\s+|[-*+]\s+|\d+[.)]\s+)", "", text)
    # Table pipes and stray markdown punctuation
    text = text.replace("|", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    """Break *text* into sentence chunks, merging tiny fragments.

    Sentence-at-a-time synthesis lets playback start almost immediately instead
    of waiting for the whole reply to be synthesised — a big perceived-latency
    win for longer answers.
    """
    text = text.strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_RE.findall(text) if p.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1]) < 40:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged or [text]


class PipelineState(StrEnum):
    """Voice pipeline states."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    CONVERSING = "conversing"


class VoicePipeline:
    """Full voice pipeline: wake -> listen -> transcribe -> respond -> converse.

    Runs in a dedicated daemon thread. Publishes user messages through
    the message bus and receives assistant responses from the
    VoiceChannel's response queue.

    Key behaviors:
    - Mic is MUTED during TTS playback to prevent echo/feedback
    - After speaking, enters CONVERSING mode where user can reply
      without saying the wake word again (like Alexa follow-up mode)
    - Conversation ends after CONVERSATION_TIMEOUT of silence
    """

    def __init__(
        self,
        config: VoiceConfig,
        bus: MessageBus,
        voice_channel: VoiceChannel,
        loop: asyncio.AbstractEventLoop,
        models_path: str = "models/",
        approval: ApprovalManager | None = None,
    ) -> None:
        self._config = config
        self._bus = bus
        self._voice_channel = voice_channel
        self._loop = loop
        self._approval = approval

        self._state = PipelineState.IDLE
        self._running = False
        self._enabled = True
        self._thread: threading.Thread | None = None

        # Sub-components
        self._capture = AudioCapture(
            sample_rate=SAMPLE_RATE,
            chunk_size=CHUNK_SIZE,
        )
        self._player = AudioPlayer()
        self._wakeword = WakeWordDetector(
            model_names=[config.wake_word_model] if config.wake_word_model else None,
            threshold=config.wake_word_threshold,
        )
        self._vad = VoiceActivityDetector(
            threshold=config.vad_threshold,
            silence_duration_ms=config.silence_duration_ms,
        )
        # In "auto" language mode, fall back to the user's primary language
        # rather than ever surfacing a mis-detected one (e.g. "ru").
        fallback_lang = config.stt_language if config.stt_language in {"es", "en"} else "es"
        self._stt = SpeechToText(
            model_size=config.stt_model,
            compute_type=config.stt_compute_type,
            language=config.stt_language,
            device=getattr(config, "stt_device", "auto"),
            beam_size=getattr(config, "stt_beam_size", 1),
            fallback_language=fallback_lang,
        )
        self._tts = build_tts(config, models_path)

        # Speaker verification (Voice ID) — only constructed when enabled. Fails
        # open at runtime if the model/profile is missing.
        self._speaker: SpeakerVerifier | None = None
        if getattr(config, "speaker_verification", False):
            self._speaker = SpeakerVerifier(
                profile_path=str(Path(models_path) / "voice_profile.npy"),
                threshold=getattr(config, "speaker_threshold", 0.65),
            )
        # In noisy/shared rooms, require the wake word for every turn instead of
        # hands-free follow-up (which can pick up other people).
        self._require_wake_each_turn = getattr(
            config, "require_wake_word_each_turn", False,
        )

        # Feature flags (best-practice defaults; see VoiceConfig).
        self._denoise = getattr(config, "denoise", True)
        self._barge_in = getattr(config, "barge_in", True)
        self._earcon_enabled = getattr(config, "earcon", True)
        self._adaptive = getattr(config, "adaptive_endpointing", True)
        self._conv_timeout = getattr(config, "conversation_timeout_s", 8)
        # Generous reply window so long multi-tool actions finish before we
        # give up on the turn (was a hard 60s → "se agotó el tiempo de espera").
        self._response_timeout = getattr(config, "response_timeout_s", 180)
        # Ask for tool confirmations out loud on voice turns.
        self._voice_confirm = getattr(config, "voice_confirm", True)
        # Register the spoken-confirmation handler with the approval manager so
        # gated tools prompt by voice instead of the (unseen) web modal.
        if self._approval is not None and self._voice_confirm:
            self._approval.set_voice_approver(self._voice_approve)

        self._speech_buffer: list[np.ndarray] = []
        self._conversation_start: float = 0.0
        self._speech_started_at: float = 0.0
        self._last_voice_at: float = 0.0
        self._listen_started_at: float = 0.0
        self._last_language = Language.AUTO
        self._last_user_text = ""
        # Monotonic per-utterance id used to correlate responses and drop stale
        # ones that arrive late from a previous (timed-out) turn.
        self._turn = 0
        # One ephemeral conversation id per wake-word activation. It scopes the
        # persisted history so each "Hey Jarvis…" starts fresh (no bleed from
        # past conversations), while follow-up turns within the same activation
        # share context. Reset to None when we return to IDLE.
        self._conversation_id: str | None = None

    # -- Properties --

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        logger.info("Voice pipeline %s", "enabled" if value else "disabled")

    # -- Lifecycle --

    def start(self) -> None:
        """Start all voice components and launch the pipeline thread."""
        logger.info("Starting voice pipeline components...")

        try:
            self._wakeword.start()
            self._vad.start()
            self._stt.start()
            self._tts.start()
            if self._speaker is not None:
                self._speaker.start()
            self._capture.start()
        except VoiceError:
            raise
        except Exception as exc:
            raise VoiceError(f"Failed to start voice pipeline: {exc}") from exc

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="voice-pipeline",
        )
        self._thread.start()
        logger.info("Voice pipeline started")

    def stop(self) -> None:
        """Stop the pipeline thread and all components."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._capture.stop()
        self._wakeword.stop()
        self._vad.stop()
        self._stt.stop()
        self._tts.stop()
        if self._speaker is not None:
            self._speaker.stop()
        logger.info("Voice pipeline stopped")

    # -- Main loop --

    def _run_loop(self) -> None:
        """State-machine loop in the voice-pipeline thread."""
        while self._running:
            if not self._enabled:
                time.sleep(0.1)
                continue

            try:
                if self._state == PipelineState.IDLE:
                    self._handle_idle()
                elif self._state == PipelineState.LISTENING:
                    self._handle_listening()
                elif self._state == PipelineState.CONVERSING:
                    self._handle_conversing()
            except Exception:
                logger.exception("Voice pipeline error — resetting to IDLE")
                self._state = PipelineState.IDLE
                self._vad.reset()
                self._wakeword.reset()
                self._drain_mic_buffer()
                time.sleep(0.5)

    # -- State handlers --

    def _handle_idle(self) -> None:
        """IDLE — listen for wake word activation."""
        # Returning to IDLE ends the conversation: drop its id so the next
        # activation starts a brand-new (history-free) session.
        self._conversation_id = None

        chunk = self._capture.read_chunk(timeout=0.5)
        if chunk is None:
            return
        detected = self._wakeword.detect(chunk)
        if detected is not None:
            logger.info("Wake word detected: %s", detected)
            # New activation → new conversation scope.
            self._conversation_id = uuid.uuid4().hex
            # Immediate audible acknowledgement (like Alexa's tone) so the user
            # knows Dax is listening before they start speaking. Mic is muted
            # during the chime so the tone is never captured as speech.
            if self._earcon_enabled:
                self._play_earcon("wake")
            self._enter_listening()

    def _handle_listening(self) -> None:
        """LISTENING — buffer audio and detect end-of-speech.

        With adaptive endpointing we track silence ourselves from the raw VAD
        probability so the end-of-speech pause shortens for quick commands and
        lengthens for longer utterances (allowing natural mid-sentence pauses).
        Falls back to Silero's VADIterator end-event when disabled.
        """
        chunk = self._capture.read_chunk(timeout=0.5)
        if chunk is None:
            return

        self._speech_buffer.append(chunk)
        float_chunk = chunk.astype(np.float32) / 32768.0

        if self._adaptive:
            if self._adaptive_endpoint(float_chunk):
                logger.info("End of speech (adaptive), transcribing...")
                self._state = PipelineState.PROCESSING
                self._process_speech()
                return
            # If the user never started speaking, don't hang forever.
            if (
                self._speech_started_at == 0.0
                and time.monotonic() - self._listen_started_at > 6.0
            ):
                logger.info("No speech after wake word — returning to IDLE")
                self._state = PipelineState.IDLE
                self._speech_buffer = []
                return
        else:
            for offset in range(0, len(float_chunk), VAD_CHUNK_SIZE):
                sub = float_chunk[offset: offset + VAD_CHUNK_SIZE]
                if len(sub) < VAD_CHUNK_SIZE:
                    sub = np.pad(sub, (0, VAD_CHUNK_SIZE - len(sub)))
                result = self._vad.process_chunk(sub)
                if result is not None and "end" in result:
                    logger.info("End of speech detected, transcribing...")
                    self._state = PipelineState.PROCESSING
                    self._process_speech()
                    return

        max_chunks = SAMPLE_RATE * _MAX_RECORDING_SECONDS // CHUNK_SIZE
        if len(self._speech_buffer) > max_chunks:
            logger.warning("Recording exceeded %d s", _MAX_RECORDING_SECONDS)
            self._state = PipelineState.PROCESSING
            self._process_speech()

    def _adaptive_endpoint(self, float_chunk: np.ndarray) -> bool:
        """Track speech/silence on *float_chunk*; return True at end-of-speech.

        Endpoint pause scales with how long the user has been speaking:
        ~450 ms for short commands, up to ~900 ms for longer utterances so
        natural pauses don't cut them off prematurely.
        """
        now = time.monotonic()
        voiced = False
        for offset in range(0, len(float_chunk), VAD_CHUNK_SIZE):
            sub = float_chunk[offset: offset + VAD_CHUNK_SIZE]
            if len(sub) < VAD_CHUNK_SIZE:
                sub = np.pad(sub, (0, VAD_CHUNK_SIZE - len(sub)))
            if self._vad.speech_prob(sub) >= self._vad.threshold:
                voiced = True

        if voiced:
            if self._speech_started_at == 0.0:
                self._speech_started_at = now
            self._last_voice_at = now
            return False

        if self._speech_started_at == 0.0:
            return False  # still waiting for speech to begin

        speech_len = self._last_voice_at - self._speech_started_at
        # Adaptive pause: short for quick commands, longer for long utterances.
        pause_s = 0.45 if speech_len < 1.2 else min(0.9, 0.45 + speech_len * 0.12)
        return (now - self._last_voice_at) >= pause_s

    def _handle_conversing(self) -> None:
        """CONVERSING — wait for follow-up speech without wake word.

        Like Alexa follow-up mode: after Dax speaks, it keeps listening
        for a few seconds. If the user speaks, transition to LISTENING.
        If silence timeout, go back to IDLE.
        """
        elapsed = time.monotonic() - self._conversation_start
        if elapsed > self._conv_timeout:
            logger.info(
                "Conversation timeout (%.0fs), returning to IDLE", elapsed,
            )
            self._state = PipelineState.IDLE
            return

        chunk = self._capture.read_chunk(timeout=0.5)
        if chunk is None:
            return

        # Detect follow-up speech start (no wake word needed).
        float_chunk = chunk.astype(np.float32) / 32768.0
        for offset in range(0, len(float_chunk), VAD_CHUNK_SIZE):
            sub = float_chunk[offset: offset + VAD_CHUNK_SIZE]
            if len(sub) < VAD_CHUNK_SIZE:
                sub = np.pad(sub, (0, VAD_CHUNK_SIZE - len(sub)))
            speaking = (
                self._vad.speech_prob(sub) >= self._vad.threshold
                if self._adaptive
                else (self._vad.process_chunk(sub) or {}).get("start") is not None
            )
            if speaking:
                logger.info("Follow-up speech detected, continuing conversation")
                self._enter_listening()
                self._speech_buffer = [chunk]
                self._speech_started_at = time.monotonic()
                self._last_voice_at = self._speech_started_at
                return

    # -- Speech processing --

    def _process_speech(self) -> None:
        """Transcribe accumulated audio and publish to the message bus."""
        if not self._speech_buffer:
            self._state = PipelineState.IDLE
            return

        raw_audio = np.concatenate(self._speech_buffer)
        float_audio = raw_audio.astype(np.float32) / 32768.0
        self._speech_buffer = []

        if self._denoise:
            float_audio = self._denoise_audio(float_audio)

        # Voice ID: drop the utterance if it isn't the enrolled owner (so other
        # people talking can't drive the assistant). Fails open if not enrolled.
        if self._speaker is not None and not self._speaker.verify(float_audio):
            logger.info("Utterance rejected by speaker verification")
            self._state = PipelineState.IDLE
            return

        try:
            text, detected_lang = self._stt.transcribe(float_audio)
        except STTError:
            logger.exception("STT failed")
            self._state = PipelineState.IDLE
            return

        if not text.strip():
            logger.info("No speech detected in audio buffer")
            self._state = PipelineState.IDLE
            return

        logger.info("Transcribed (%s): %s", detected_lang, text)
        language = self._map_language(detected_lang)
        self._last_language = language
        self._last_user_text = text

        self._turn += 1
        # Ensure a conversation scope exists (defensive — wake sets it).
        if self._conversation_id is None:
            self._conversation_id = uuid.uuid4().hex
        message = Message(
            role=MessageRole.USER,
            content=text,
            channel=ChannelType.VOICE,
            language=language,
            metadata={
                "voice_turn": str(self._turn),
                "session_id": self._conversation_id,
            },
        )

        # Discard any response left over from a previous (e.g. timed-out) turn
        # so we never speak a stale answer to this new question.
        try:
            asyncio.run_coroutine_threadsafe(
                self._voice_channel.drain(), self._loop,
            ).result(timeout=2)
        except Exception:
            logger.debug("Voice queue drain failed", exc_info=True)

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._bus.publish_inbound(message), self._loop,
            )
            future.result(timeout=5)
        except Exception:
            logger.exception("Failed to publish inbound message")
            self._state = PipelineState.IDLE
            return

        self._wait_and_speak(language)

    def _wait_and_speak(self, language: Language) -> None:
        """Wait for the assistant's response and speak it.

        Speaks sentence by sentence for low time-to-first-audio. When barge-in
        is enabled the mic stays live during playback and the wake word
        interrupts Dax mid-reply (so you can cut him off, like Alexa). When
        disabled, the mic is muted during playback to avoid echo/feedback.
        After speaking, enters CONVERSING mode for follow-up.
        """
        self._state = PipelineState.SPEAKING

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._voice_channel.get_response(
                    timeout=float(self._response_timeout),
                    expected_turn=str(self._turn),
                ),
                self._loop,
            )
            response: Message | None = future.result(timeout=self._response_timeout + 10)

            if response is None:
                logger.warning("Timed out waiting for assistant response")
                self._state = PipelineState.IDLE
                return

            logger.info("Speaking response: %.80s...", response.content)

            tts_lang = "en"
            if language == Language.SPANISH or response.language == Language.SPANISH:
                tts_lang = "es"

            interrupted = self._speak(response.content, tts_lang)

            if interrupted:
                logger.info("Barge-in detected — listening to the user")
                self._drain_mic_buffer()
                self._enter_listening()
                return

            # End the conversation only when the USER said goodbye — not when
            # Dax's reply happens to contain filler like "listo".
            if self._is_farewell(self._last_user_text):
                logger.info("Farewell detected, ending conversation")
                self._state = PipelineState.IDLE
            elif self._require_wake_each_turn:
                # No hands-free follow-up: wait for the wake word again.
                self._state = PipelineState.IDLE
            else:
                self._enter_conversing()

        except TTSError:
            logger.exception("TTS synthesis failed")
            self._state = PipelineState.IDLE
        except Exception:
            logger.exception("Error during speech playback")
            self._state = PipelineState.IDLE

    def _speak(self, text: str, tts_lang: str) -> bool:
        """Synthesise and play *text*. Returns True if interrupted (barge-in)."""
        sentences = _split_sentences(_clean_for_speech(text))

        if not self._barge_in:
            # Mute the mic during playback to prevent echo/feedback.
            self._capture.stop()
            self._drain_mic_buffer()
            try:
                for sentence in sentences:
                    audio = self._tts.synthesize(sentence, language=tts_lang)
                    self._player.play(audio, sample_rate=self._tts.sample_rate)
            finally:
                time.sleep(0.3)
                self._capture.start()
            return False

        # Barge-in: keep the mic live and let the wake word interrupt playback.
        self._drain_mic_buffer()
        self._wakeword.reset()
        interrupted = False
        for sentence in sentences:
            audio = self._tts.synthesize(sentence, language=tts_lang)
            interrupted = self._player.play_blocks(
                audio,
                sample_rate=self._tts.sample_rate,
                should_stop=self._bargein_detected,
            )
            if interrupted:
                break
        self._wakeword.reset()
        return interrupted

    def _bargein_detected(self) -> bool:
        """True if the wake word is heard while Dax is speaking (interrupt)."""
        for _ in range(4):
            chunk = self._capture.read_chunk(timeout=0.0)
            if chunk is None:
                break
            if self._wakeword.detect(chunk) is not None:
                return True
        return False

    # -- Spoken confirmation (voice approval) --

    async def _voice_approve(
        self,
        *,
        tool_name: str,
        server_name: str | None = None,
        arguments: dict[str, object] | None = None,
        options: list[str] | None = None,
    ) -> str:
        """Ask the user to confirm a tool by voice; return the decision.

        Runs the blocking speak+listen cycle in a worker thread so the event
        loop (and the rest of the agent) isn't stalled. Called by the
        ApprovalManager when a gated tool originates from the voice channel.
        """
        return await self._loop.run_in_executor(
            None, self._confirm_blocking, tool_name, options or [],
        )

    def _confirm_blocking(self, tool_name: str, options: list[str]) -> str:
        """Speak a yes/no question, listen for the answer, map to a decision."""
        lang = "es" if self._last_language == Language.SPANISH else "en"
        self._speak_now(self._confirm_question(tool_name, lang), lang)

        audio = self._record_utterance(max_seconds=6.0)
        if audio is None or audio.size == 0:
            logger.info("No confirmation heard — denying")
            return "deny"
        try:
            text, _ = self._stt.transcribe(audio)
        except STTError:
            logger.exception("Confirmation STT failed — denying")
            return "deny"
        logger.info("Confirmation heard: %r", text)
        return self._parse_yes_no(text, options)

    @staticmethod
    def _confirm_question(tool_name: str, lang: str) -> str:
        """The spoken yes/no prompt for a gated tool."""
        if lang == "es":
            return f"¿Quieres que ejecute {tool_name}? Di sí o no."
        return f"Do you want me to run {tool_name}? Say yes or no."

    def _speak_now(self, text: str, lang: str) -> None:
        """Synthesise and play *text* immediately, mic muted (no barge-in)."""
        self._capture.stop()
        self._drain_mic_buffer()
        try:
            audio = self._tts.synthesize(text, language=lang)
            self._player.play(audio, sample_rate=self._tts.sample_rate)
        finally:
            time.sleep(0.2)
            self._capture.start()
            self._drain_mic_buffer()

    def _record_utterance(self, max_seconds: float = 6.0) -> np.ndarray | None:
        """Record a single short utterance and return float32 audio.

        Waits briefly for speech to begin, then captures until a short silence
        (using Silero ``speech_prob``) or ``max_seconds`` elapses. Returns None
        if the user never spoke.
        """
        self._vad.reset()
        chunks: list[np.ndarray] = []
        started_at = 0.0
        last_voice_at = 0.0
        deadline = time.monotonic() + max_seconds
        while time.monotonic() < deadline:
            chunk = self._capture.read_chunk(timeout=0.5)
            if chunk is None:
                continue
            chunks.append(chunk)
            float_chunk = chunk.astype(np.float32) / 32768.0
            voiced = False
            for offset in range(0, len(float_chunk), VAD_CHUNK_SIZE):
                sub = float_chunk[offset: offset + VAD_CHUNK_SIZE]
                if len(sub) < VAD_CHUNK_SIZE:
                    sub = np.pad(sub, (0, VAD_CHUNK_SIZE - len(sub)))
                if self._vad.speech_prob(sub) >= self._vad.threshold:
                    voiced = True
            now = time.monotonic()
            if voiced:
                if started_at == 0.0:
                    started_at = now
                last_voice_at = now
            elif started_at != 0.0 and (now - last_voice_at) >= 0.6:
                break  # end of the answer
        if started_at == 0.0:
            return None
        return np.concatenate(chunks).astype(np.float32) / 32768.0

    @staticmethod
    def _parse_yes_no(text: str, options: list[str]) -> str:
        """Map a spoken answer to a decision string (es/en)."""
        lower = text.lower().strip()
        yes = {
            "sí", "si", "claro", "dale", "hazlo", "ok", "okay", "vale",
            "adelante", "confirmo", "confirmar", "yes", "yeah", "yep",
            "sure", "go ahead", "do it", "confirm", "affirmative",
        }
        no = {
            "no", "nop", "negativo", "cancela", "cancelar", "para", "detente",
            "nope", "cancel", "stop", "don't", "negative",
        }
        tokens = set(re.findall(r"[\wáéíóúñ']+", lower))
        is_yes = bool(tokens & yes) or any(p in lower for p in ("go ahead", "do it"))
        is_no = bool(tokens & no)
        if is_no and not is_yes:
            return "deny"
        if is_yes:
            return "once" if "once" in options else "approve"
        # Ambiguous → fail safe.
        return "deny"

    def _denoise_audio(self, audio: np.ndarray) -> np.ndarray:
        """Reduce background noise before STT (best-effort; needs noisereduce)."""
        try:
            import noisereduce as nr

            reduced = nr.reduce_noise(y=audio, sr=SAMPLE_RATE, stationary=False)
            return np.asarray(reduced, dtype=np.float32)
        except Exception:
            logger.debug("Denoise unavailable/failed — using raw audio", exc_info=True)
            return audio

    # -- State transitions --

    def _enter_listening(self) -> None:
        """Transition to LISTENING state."""
        self._state = PipelineState.LISTENING
        self._vad.reset()
        self._speech_buffer = []
        self._speech_started_at = 0.0
        self._last_voice_at = 0.0
        self._listen_started_at = time.monotonic()

    def _enter_conversing(self) -> None:
        """Transition to CONVERSING state (follow-up mode)."""
        self._state = PipelineState.CONVERSING
        self._conversation_start = time.monotonic()
        self._vad.reset()
        self._drain_mic_buffer()  # discard any TTS tail before listening
        logger.info(
            "Conversation mode — listening for follow-up (%ds timeout)",
            self._conv_timeout,
        )

    # -- Earcons --

    def _play_earcon(self, kind: str = "wake") -> None:
        """Play a short confirmation tone with the mic muted.

        A wake earcon gives instant feedback (Alexa-style) the moment the wake
        word fires, so the user knows to start speaking. Best-effort: any audio
        error is swallowed so it never blocks the conversation.
        """
        try:
            tone = self._earcon_samples(kind)
            self._capture.stop()
            self._drain_mic_buffer()
            try:
                self._player.play(tone, sample_rate=22_050)
            finally:
                time.sleep(0.05)
                self._capture.start()
                self._drain_mic_buffer()
        except Exception:
            logger.debug("Earcon playback failed", exc_info=True)

    @staticmethod
    def _earcon_samples(kind: str) -> np.ndarray:
        """Synthesise a short two-note chime as int16 PCM at 22.05 kHz."""
        sr = 22_050
        # (frequency_hz, duration_s) — a rising pair for "wake", soft for "end".
        notes = [(880.0, 0.09), (1320.0, 0.11)] if kind == "wake" else [(660.0, 0.12)]
        segments: list[np.ndarray] = []
        for freq, dur in notes:
            t = np.linspace(0, dur, int(sr * dur), endpoint=False)
            wave = np.sin(2 * np.pi * freq * t)
            # Short fade in/out to avoid clicks.
            fade = max(1, int(sr * 0.01))
            env = np.ones_like(wave)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            segments.append(wave * env * 0.3)
        audio = np.concatenate(segments)
        return (audio * 32767).astype(np.int16)

    # -- Helpers --

    def _drain_mic_buffer(self) -> None:
        """Discard any buffered audio chunks from the mic queue."""
        while self._capture.read_chunk(timeout=0.01) is not None:
            pass

    @staticmethod
    def _map_language(detected: str) -> Language:
        """Map a Whisper language code to the domain Language enum."""
        if detected == "es":
            return Language.SPANISH
        if detected == "en":
            return Language.ENGLISH
        return Language.AUTO

    @staticmethod
    def _is_farewell(text: str) -> bool:
        """Detect if text is a conversation-ending farewell.

        Checks both the user's input and the assistant's response for
        farewell patterns. When detected, the pipeline skips CONVERSING
        mode and returns directly to IDLE.
        """
        farewell_patterns = {
            # Spanish
            "chao", "chau", "adiós", "adios", "hasta luego",
            "hasta pronto", "nos vemos", "buenas noches",
            # English
            "bye", "goodbye", "good bye", "see you", "see ya",
            "take care", "good night", "that's all", "thats all",
            # Polite closers (user-side only; "listo" removed — Dax says it
            # constantly as filler and it must not end the conversation).
            "gracias", "thanks", "thank you", "eso es todo",
        }
        lower = text.lower().strip()
        # Check if the response is short AND contains a farewell
        if len(lower.split()) > 15:
            return False
        return any(pattern in lower for pattern in farewell_patterns)
