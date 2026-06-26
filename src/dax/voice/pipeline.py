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
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np

from dax.core.exceptions import STTError, TTSError, VoiceError
from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.voice.audio_io import CHUNK_SIZE, SAMPLE_RATE, AudioCapture, AudioPlayer
from dax.voice.stt import SpeechToText
from dax.voice.tts import TextToSpeech
from dax.voice.vad import VAD_CHUNK_SIZE, VoiceActivityDetector
from dax.voice.wakeword import WakeWordDetector

if TYPE_CHECKING:
    from dax.channels.voice_channel import VoiceChannel
    from dax.core.config import VoiceConfig
    from dax.orchestrator.bus import MessageBus

logger = logging.getLogger(__name__)

# Safety limits
_MAX_RECORDING_SECONDS = 30


# Split assistant text into sentence-ish chunks for incremental TTS playback.
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]*")


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
    ) -> None:
        self._config = config
        self._bus = bus
        self._voice_channel = voice_channel
        self._loop = loop

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
        self._wakeword = WakeWordDetector(threshold=config.wake_word_threshold)
        self._vad = VoiceActivityDetector(
            threshold=config.vad_threshold,
            silence_duration_ms=config.silence_duration_ms,
        )
        self._stt = SpeechToText(
            model_size=config.stt_model,
            compute_type=config.stt_compute_type,
            language=config.stt_language,
            device=getattr(config, "stt_device", "auto"),
            beam_size=getattr(config, "stt_beam_size", 1),
        )
        self._tts = TextToSpeech(
            voice_es=config.tts_voice_es,
            voice_en=config.tts_voice_en,
        )

        # Feature flags (best-practice defaults; see VoiceConfig).
        self._denoise = getattr(config, "denoise", True)
        self._barge_in = getattr(config, "barge_in", True)
        self._earcon_enabled = getattr(config, "earcon", True)
        self._adaptive = getattr(config, "adaptive_endpointing", True)
        self._conv_timeout = getattr(config, "conversation_timeout_s", 8)

        self._speech_buffer: list[np.ndarray] = []
        self._conversation_start: float = 0.0
        self._speech_started_at: float = 0.0
        self._last_voice_at: float = 0.0
        self._listen_started_at: float = 0.0
        self._last_language = Language.AUTO

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
        chunk = self._capture.read_chunk(timeout=0.5)
        if chunk is None:
            return
        detected = self._wakeword.detect(chunk)
        if detected is not None:
            logger.info("Wake word detected: %s", detected)
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

        message = Message(
            role=MessageRole.USER,
            content=text,
            channel=ChannelType.VOICE,
            language=language,
        )

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
                self._voice_channel.get_response(timeout=30.0),
                self._loop,
            )
            response: Message | None = future.result(timeout=35)

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

            # Check if the response is a farewell — if so, end conversation
            if self._is_farewell(response.content):
                logger.info("Farewell detected, ending conversation")
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
        sentences = _split_sentences(text)

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

    def _denoise_audio(self, audio: np.ndarray) -> np.ndarray:
        """Reduce background noise before STT (best-effort; needs noisereduce)."""
        try:
            import noisereduce as nr  # type: ignore[import-not-found]

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
            # Universal
            "listo", "gracias", "thanks", "thank you",
        }
        lower = text.lower().strip()
        # Check if the response is short AND contains a farewell
        if len(lower.split()) > 15:
            return False
        return any(pattern in lower for pattern in farewell_patterns)
