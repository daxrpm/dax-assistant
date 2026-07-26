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
import queue
import re
import threading
import time
import uuid
from collections import deque
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np

from dax.core.exceptions import STTError, TTSError, VoiceError
from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.core.voice_events import LevelSource, VoiceEventHub
from dax.llm.client import sanitize_assistant_text
from dax.voice.arbiter import HOST_SOURCE_ID, WakeArbiter
from dax.voice.audio_io import CHUNK_SIZE, SAMPLE_RATE, AudioCapture, AudioPlayer, AudioSource
from dax.voice.events import emit_level
from dax.voice.speaker import SpeakerVerifier
from dax.voice.stt import build_stt
from dax.voice.tts_service import TTSService
from dax.voice.vad import VAD_CHUNK_SIZE, VoiceActivityDetector
from dax.voice.wakeword import WakeWordDetector

if TYPE_CHECKING:
    from collections.abc import Callable

    from dax.channels.voice_channel import VoiceChannel
    from dax.core.config import VoiceConfig
    from dax.orchestrator.approval import ApprovalManager
    from dax.orchestrator.bus import MessageBus

logger = logging.getLogger(__name__)

# Safety limits
_MAX_RECORDING_SECONDS = 30

# How much silence may interrupt a follow-up utterance before the accumulated
# speech is discarded. Covers the micro-pauses of natural speech onset.
_FOLLOWUP_GAP_TOLERANCE_MS = 400

# Minimum voiced audio before a gap is tolerated at all. Below this the signal
# is an isolated VAD spike, not speech, and is discarded on the first quiet
# frame so background noise never accumulates a phantom utterance.
_FOLLOWUP_MIN_SPEECH_MS = 160

# How many recent turns feed the STT biasing prompt. Whisper's prompt budget is
# small (224 tokens), so this stays tight and recency-weighted.
_STT_CONTEXT_TURNS = 4


# Split assistant text into sentence-ish chunks for incremental TTS playback.
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]*")


def _clean_for_speech(text: str) -> str:
    """Strip markdown so the TTS doesn't read symbols like '**' aloud.

    Belt-and-suspenders alongside the voice system prompt: even if the model
    emits markdown, the synthesizer should speak clean prose.
    """
    text = sanitize_assistant_text(text)
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


def _ends_with_question(text: str) -> bool:
    """True if *text* closes on a question.

    Used to widen the follow-up window: when Dax asks something he has invited
    a reply, and the default timeout is too short to formulate one.
    """
    stripped = _clean_for_speech(text).rstrip().rstrip("\"'")
    return stripped.endswith("?")


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


class _PTTCommand:
    """One cross-thread push-to-talk transition and its acknowledgement."""

    def __init__(self, action: Literal["press", "release", "cancel"]) -> None:
        self.action = action
        self.done = threading.Event()
        self.cancelled = threading.Event()
        self.error: str | None = None
        self.state = PipelineState.IDLE


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
        events: VoiceEventHub | None = None,
        tts_service: TTSService | None = None,
    ) -> None:
        self._config = config
        self._bus = bus
        self._voice_channel = voice_channel
        self._loop = loop
        self._approval = approval
        # Event fan-out to UI clients. Defaults to a detached hub so the
        # pipeline never has to null-check before emitting.
        self._events = events if events is not None else VoiceEventHub(loop)
        self._events.bind_loop(loop)

        # Backing field for the _state property below. Assigned directly here so
        # __init__ does not fire a transition event before the object exists.
        self.__state = PipelineState.IDLE
        self._running = False
        self._ptt_active = False
        self._enabled = True
        self._thread: threading.Thread | None = None
        self._ptt_commands: queue.SimpleQueue[_PTTCommand] = queue.SimpleQueue()
        self._ptt_active = False

        # Sub-components
        self._capture = AudioCapture(
            sample_rate=SAMPLE_RATE,
            chunk_size=CHUNK_SIZE,
        )
        self._audio_source: AudioSource = self._capture
        self._source_lock = threading.Lock()
        self._player = AudioPlayer()
        # Lease id of the client that owns spoken output, or None when the
        # backend host's own speakers do. See set_output_owner().
        self._output_owner: str | None = None
        # A remote lease owns input, output and every event as one exclusive
        # context. Only one pipeline exists; leases never create another one.
        self._input_owner: str | None = None
        self._owner_generation = 0
        self._wakeword = WakeWordDetector(
            model_names=[config.wake_word_model] if config.wake_word_model else None,
            threshold=config.wake_word_threshold,
        )
        self._vad = VoiceActivityDetector(
            threshold=config.vad_threshold,
            silence_duration_ms=config.silence_duration_ms,
        )
        self._stt = build_stt(config)
        self._tts = tts_service if tts_service is not None else TTSService(config, models_path)

        # Speaker verification (Voice ID) — only constructed when enabled. Fails
        # open at runtime if the model/profile is missing.
        self._speaker: SpeakerVerifier | None = None
        if getattr(config, "speaker_verification", False):
            self._speaker = SpeakerVerifier(
                profile_path=str(Path(models_path) / "voice_profile.npy"),
                threshold=getattr(config, "speaker_threshold", 0.65),
                fail_open=getattr(config, "speaker_fail_open", True),
            )
        # In noisy/shared rooms, require the wake word for every turn instead of
        # hands-free follow-up (which can pick up other people).
        self._require_wake_each_turn = getattr(
            config,
            "require_wake_word_each_turn",
            False,
        )
        # How long a voice session survives between activations. Beyond this,
        # the next wake word starts a history-free conversation.
        self._session_ttl_s = max(0.0, getattr(config, "session_ttl_minutes", 10) * 60.0)

        # Feature flags (best-practice defaults; see VoiceConfig).
        self._denoise = getattr(config, "denoise", True)
        self._barge_in = getattr(config, "barge_in", True)
        self._earcon_enabled = getattr(config, "earcon", True)
        self._adaptive = getattr(config, "adaptive_endpointing", True)
        self._silence_s = max(0.25, min(1.5, config.silence_duration_ms / 1000))
        self._conv_timeout = getattr(config, "conversation_timeout_s", 8)
        self._conv_timeout_question = max(
            self._conv_timeout,
            getattr(config, "conversation_timeout_question_s", 20),
        )
        self._followup_activation_ms = max(80, getattr(config, "followup_activation_ms", 320))
        self._thinking_pause_s = max(
            0.0, min(3.0, getattr(config, "thinking_pause_ms", 900) / 1000)
        )
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
        self._response_future: object | None = None
        # One ephemeral conversation id per wake-word activation. It scopes the
        # persisted history so each "Hey Jarvis…" starts fresh (no bleed from
        # past conversations), while follow-up turns within the same activation
        # share context. Reset to None when we return to IDLE.
        self._conversation_id: str | None = None
        # Wall-clock of the last voice turn, used to decide whether the next
        # wake word resumes the current session or starts a new one.
        self._session_last_activity: float = 0.0
        self._followup_buffer: list[np.ndarray] = []
        self._followup_voiced_ms = 0
        self._followup_silence_ms = 0
        # Whether Dax's last reply ended in a question. When he asks something,
        # he has invited an answer, so the follow-up window stays open longer.
        self._last_reply_was_question = False
        # Armed by a manual activation and consumed when its single automatic
        # follow-up starts. A follow-up response can therefore never self-chain.
        self._followup_armed = False
        # Recent turn text, oldest first, used to bias the next transcription
        # toward the vocabulary already in play.
        self._recent_turns: deque[str] = deque(maxlen=_STT_CONTEXT_TURNS)

        # Wake arbitration. The host microphone is one claimant among several;
        # capability nodes claim through the hub against this same arbiter, so
        # a single "hey jarvis" heard in two places produces one answer.
        self._arbiter = WakeArbiter(
            window_s=max(0, config.wake_arbitration_window_ms) / 1000.0,
            suppress_s=max(0, config.wake_suppress_ms) / 1000.0,
        )
        # Set by the hub when a node wins; consumed by the state machine thread.
        self._remote_wake_owner: str | None = None
        self._wake_holder: str | None = None
        self._remote_wake_end: Callable[[str], None] | None = None
        self._wake_lock = threading.Lock()

    # -- Properties --

    @property
    def _state(self) -> PipelineState:
        """Current state. Assigning to it broadcasts the transition.

        Defined as a property so the ~20 ``self._state = ...`` assignments
        scattered through the state handlers stay untouched and can never
        forget to notify listeners.
        """
        return self.__state

    @_state.setter
    def _state(self, value: PipelineState) -> None:
        if value == self.__state:
            return
        self.__state = value
        # Returning to IDLE ends the turn the wake word started, so whoever won
        # that arbitration stops holding the wake path. Doing it here rather
        # than at each of the ~20 transition sites is what makes it impossible
        # to leave the arbiter wedged down an error path.
        if value == PipelineState.IDLE:
            self._release_wake_hold()
        expires_at: float | None = None
        if self._conversation_id is not None and self._session_ttl_s > 0:
            remaining = max(
                0.0,
                self._session_last_activity + self._session_ttl_s - time.monotonic(),
            )
            expires_at = time.time() + remaining
        self._events.emit_state(str(value), self._conversation_id, session_expires_at=expires_at)

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def events(self) -> VoiceEventHub:
        """The hub UI clients subscribe to for state and level frames."""
        return self._events

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
            target=self._run_loop,
            daemon=True,
            name="voice-pipeline",
        )
        self._thread.start()
        logger.info("Voice pipeline started")

    def stop(self) -> None:
        """Stop the pipeline thread and all components."""
        self._running = False
        self._fail_pending_ptt("Voice pipeline is stopping")
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

    def push_to_talk_press(self, timeout: float = 2.0) -> PipelineState:
        """Start local capture without a wake word, safely on the voice thread."""
        return self._request_ptt("press", timeout)

    def push_to_talk_release(self, timeout: float = 2.0) -> PipelineState:
        """Finalize local capture and schedule processing on the voice thread."""
        return self._request_ptt("release", timeout)

    def push_to_talk_cancel(self, timeout: float = 2.0) -> PipelineState:
        """Abort an incomplete PTT utterance without sending it to STT."""
        return self._request_ptt("cancel", timeout)

    def interrupt_remote_turn(self) -> PipelineState:
        """Invalidate remote delivery and make the pipeline accept a new turn.

        This deliberately does not claim to cancel agent or tool execution;
        that work may finish in the background. It only cancels the response
        waiter and advances the correlation id so its late output is never
        spoken or treated as the next turn.
        """
        if self._output_owner is None:
            raise VoiceError("Remote output is not owned")
        self._turn += 1
        future = self._response_future
        if future is not None:
            cancel = getattr(future, "cancel", None)
            if cancel is not None:
                cancel()
        self._ptt_active = False
        self._state = PipelineState.IDLE
        return self._state

    def set_output_owner(self, owner: str | None) -> None:
        """Hand spoken output to a remote client, or take it back with ``None``.

        A phone is the case this exists for: the user is not standing next to
        the backend host, so synthesising and playing there would answer into
        an empty room. While a client owns output the pipeline still emits
        ``speech`` events per sentence — the client synthesises them locally —
        and skips synthesis and playback entirely. That makes the remote case
        *cheaper* on the server than the local one, not more expensive.
        """
        self._output_owner = owner
        logger.info(
            "Voice output owned by %s", owner if owner is not None else "the backend host"
        )

    @property
    def output_owner(self) -> str | None:
        return self._output_owner

    @property
    def input_owner(self) -> str | None:
        return self._input_owner

    @property
    def owner_generation(self) -> int:
        return self._owner_generation

    def acquire_remote_owner(self, owner: str) -> int:
        """Exclusively isolate the existing pipeline for one remote lease."""
        if self._state != PipelineState.IDLE or self._ptt_active:
            raise VoiceError(f"Voice pipeline is busy ({self._state})")
        if self._input_owner is not None and self._input_owner != owner:
            raise VoiceError("Remote voice is owned by another client")
        self._reset_conversation_context()
        self._input_owner = owner
        self._output_owner = owner
        self._owner_generation = self._events.set_event_owner(owner)
        logger.info("Voice input, output and events owned by %s", owner)
        return self._owner_generation

    def release_remote_owner(self, owner: str) -> None:
        """Restore host I/O after an idle remote lease has fully settled."""
        if self._input_owner != owner:
            return
        if self._state != PipelineState.IDLE or self._ptt_active:
            raise VoiceError(f"Cannot release remote voice while pipeline is {self._state}")
        with self._source_lock:
            self._audio_source = self._capture
        self._reset_conversation_context()
        self._input_owner = None
        self._output_owner = None
        self._owner_generation = self._events.set_event_owner(None)
        logger.info("Voice input, output and events restored to the backend host")

    def select_audio_source(self, source: AudioSource | None) -> None:
        """Select a source while idle; ``None`` restores the local microphone."""
        if self._ptt_active or self._state in {
            PipelineState.LISTENING,
            PipelineState.CONVERSING,
        }:
            raise VoiceError(f"Cannot switch audio source while pipeline is {self._state}")
        selected = source if source is not None else self._capture
        with self._source_lock:
            self._audio_source = selected

    # -- Wake arbitration --

    @property
    def arbiter(self) -> WakeArbiter:
        """The referee node claims are judged against, shared with the hub."""
        return self._arbiter

    def set_remote_wake_end_callback(
        self, callback: Callable[[str], None] | None
    ) -> None:
        """Register who to tell when a node-owned wake turn is over.

        Only the pipeline knows where the sentence ended, and only the hub can
        reach the node, so the two are joined by this one callback rather than
        by either holding the other.
        """
        self._remote_wake_end = callback

    def request_remote_wake(self, owner: str) -> None:
        """Open a turn for a node that won the wake and is now streaming.

        Called from the event loop, consumed by the pipeline thread. The caller
        is responsible for having taken the remote lease and selected the audio
        source first, so that by the time the turn opens there is already audio
        arriving to transcribe.
        """
        with self._wake_lock:
            self._remote_wake_owner = owner
            self._wake_holder = owner

    def _take_remote_wake_request(self) -> str | None:
        with self._wake_lock:
            owner, self._remote_wake_owner = self._remote_wake_owner, None
            return owner

    def _claim_wake(self, source_id: str, score: float) -> bool:
        """Bid for the right to answer, and record the hold when it is won."""
        won = self._arbiter.wait_for(self._arbiter.claim(source_id, score))
        if won:
            with self._wake_lock:
                self._wake_holder = source_id
        return won

    def _release_wake_hold(self) -> None:
        with self._wake_lock:
            holder, self._wake_holder = self._wake_holder, None
            callback = self._remote_wake_end
        if holder is None:
            return
        self._arbiter.release(holder)
        if holder != HOST_SOURCE_ID and callback is not None:
            # Never let a listener's failure strand the pipeline in a state it
            # has already left.
            try:
                callback(holder)
            except Exception:
                logger.exception("Remote wake-end callback failed for %s", holder)

    def _request_ptt(
        self, action: Literal["press", "release", "cancel"], timeout: float
    ) -> PipelineState:
        if not self._running or not self._enabled:
            raise VoiceError("Voice input is not available")
        if action == "press":
            if self._ptt_active:
                return self._state
            if self._state != PipelineState.IDLE:
                raise VoiceError(f"Voice pipeline is busy ({self._state})")
        command = _PTTCommand(action)
        self._ptt_commands.put(command)
        if not command.done.wait(timeout):
            command.cancelled.set()
            raise VoiceError("Voice pipeline did not accept push-to-talk in time")
        if command.error is not None:
            raise VoiceError(command.error)
        return command.state

    # -- Main loop --

    def _run_loop(self) -> None:
        """State-machine loop in the voice-pipeline thread."""
        while self._running:
            if not self._enabled:
                time.sleep(0.1)
                continue

            try:
                self._drain_ptt_commands()
                if self._state == PipelineState.IDLE:
                    self._handle_idle()
                elif self._state == PipelineState.LISTENING:
                    self._handle_listening()
                elif self._state == PipelineState.CONVERSING:
                    self._handle_conversing()
            except Exception as exc:
                logger.exception("Voice pipeline error — resetting to IDLE")
                self._events.emit_error(str(exc))
                self._ptt_active = False
                self._arbiter.reset()
                self._state = PipelineState.IDLE
                self._vad.reset()
                self._wakeword.reset()
                self._drain_mic_buffer()
                time.sleep(0.5)

        self._fail_pending_ptt("Voice pipeline stopped")

    def _drain_ptt_commands(self) -> None:
        """Apply external PTT commands only from the state-machine thread."""
        while True:
            try:
                command = self._ptt_commands.get_nowait()
            except queue.Empty:
                return

            if command.cancelled.is_set():
                continue

            process_audio = False
            try:
                if command.action == "press":
                    if self._ptt_active:
                        pass  # Key-repeat is idempotent.
                    elif self._state != PipelineState.IDLE:
                        command.error = f"Voice pipeline is busy ({self._state})"
                    else:
                        self._ptt_active = True
                        self._followup_armed = True
                        self._resume_or_start_session()
                        self._enter_listening()
                        logger.info("Push-to-talk capture started")
                elif command.action == "cancel":
                    self._ptt_active = False
                    self._speech_buffer = []
                    if self._state == PipelineState.LISTENING:
                        self._state = PipelineState.IDLE
                    logger.info("Push-to-talk capture cancelled")
                elif self._ptt_active:
                    self._ptt_active = False
                    self._drain_remote_ptt_tail()
                    if self._state == PipelineState.LISTENING and self._speech_buffer:
                        self._state = PipelineState.PROCESSING
                        process_audio = True
                        logger.info("Push-to-talk capture released; processing audio")
                    elif self._state == PipelineState.LISTENING:
                        self._state = PipelineState.IDLE
                        logger.info("Push-to-talk released without audio")
                command.state = self._state
            except Exception as exc:
                command.error = str(exc)
            finally:
                # Release the HTTP request before STT/LLM/TTS starts blocking.
                command.done.set()

            if process_audio:
                self._process_speech()

    def _fail_pending_ptt(self, message: str) -> None:
        while True:
            try:
                command = self._ptt_commands.get_nowait()
            except queue.Empty:
                return
            command.error = message
            command.done.set()

    # -- State handlers --

    def _handle_idle(self) -> None:
        """IDLE — listen for wake word activation.

        Note the session id is deliberately *not* cleared here. Returning to
        IDLE ends the hands-free follow-up window, not the conversation;
        :meth:`_resume_or_start_session` decides on the next wake word whether
        enough time has passed to warrant forgetting.
        """
        # A node that won the arbitration is already streaming its microphone
        # into the selected audio source; all that is left is to open the turn.
        remote_owner = self._take_remote_wake_request()
        if remote_owner is not None:
            logger.info("Wake word granted to node %s", remote_owner)
            self._resume_or_start_session()
            self._followup_armed = True
            self._enter_listening()
            return

        # A remote output lease means the user is at that client, not beside
        # this machine. Never sample the host microphone while it is held.
        if self._output_owner is not None:
            time.sleep(0.05)
            return
        chunk = self._read_metered_chunk(timeout=0.5)
        if chunk is None:
            return
        detection = self._wakeword.detect_with_score(chunk)
        if detection is None:
            return
        detected, score = detection
        logger.info("Wake word detected: %s (score=%.3f)", detected, score)

        # Another microphone may have heard the same words more clearly. Wait
        # for the verdict before making any sound, so a losing host never emits
        # an earcon the winning node is about to emit too.
        if not self._claim_wake(HOST_SOURCE_ID, score):
            logger.info("Another microphone answered — standing down")
            self._wakeword.reset()
            self._drain_mic_buffer()
            return

        self._resume_or_start_session()
        self._followup_armed = True
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
        chunk = self._read_metered_chunk(timeout=0.5)
        if chunk is None:
            return

        self._speech_buffer.append(chunk)
        if self._ptt_active:
            # PTT owns endpointing: silence and the wake-word timeout must not
            # end capture while the physical key remains held.
            max_chunks = SAMPLE_RATE * _MAX_RECORDING_SECONDS // CHUNK_SIZE
            if len(self._speech_buffer) > max_chunks:
                self._ptt_active = False
                self._state = PipelineState.PROCESSING
                self._process_speech()
            return
        float_chunk = chunk.astype(np.float32) / 32768.0

        if self._adaptive:
            if self._adaptive_endpoint(float_chunk):
                logger.info("End of speech (adaptive), transcribing...")
                self._state = PipelineState.PROCESSING
                self._process_speech()
                return
            # If the user never started speaking, don't hang forever.
            if self._speech_started_at == 0.0 and time.monotonic() - self._listen_started_at > 6.0:
                logger.info("No speech after wake word — returning to IDLE")
                self._state = PipelineState.IDLE
                self._speech_buffer = []
                return
        else:
            for offset in range(0, len(float_chunk), VAD_CHUNK_SIZE):
                sub = float_chunk[offset : offset + VAD_CHUNK_SIZE]
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
            sub = float_chunk[offset : offset + VAD_CHUNK_SIZE]
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
        # The configured silence duration is the baseline; longer utterances get
        # a separate thinking allowance so natural pauses are not clipped.
        pause_s = self._silence_s
        if speech_len >= 1.2:
            pause_s += self._thinking_pause_s
        return (now - self._last_voice_at) >= pause_s

    def _handle_conversing(self) -> None:
        """CONVERSING — wait for follow-up speech without wake word.

        Like Alexa follow-up mode: after Dax speaks, it keeps listening
        for a few seconds. If the user speaks, transition to LISTENING.
        If silence timeout, go back to IDLE.
        """
        timeout = (
            self._conv_timeout_question if self._last_reply_was_question else self._conv_timeout
        )
        elapsed = time.monotonic() - self._conversation_start
        if elapsed > timeout:
            logger.info(
                "Conversation timeout (%.0fs of %ds), returning to IDLE",
                elapsed,
                timeout,
            )
            self._state = PipelineState.IDLE
            return

        chunk = self._read_metered_chunk(timeout=0.5)
        if chunk is None:
            return

        # Detect follow-up speech start (no wake word needed).
        float_chunk = chunk.astype(np.float32) / 32768.0
        voiced = False
        for offset in range(0, len(float_chunk), VAD_CHUNK_SIZE):
            sub = float_chunk[offset : offset + VAD_CHUNK_SIZE]
            if len(sub) < VAD_CHUNK_SIZE:
                sub = np.pad(sub, (0, VAD_CHUNK_SIZE - len(sub)))
            speaking = (
                self._vad.speech_prob(sub) >= self._vad.threshold
                if self._adaptive
                else (self._vad.process_chunk(sub) or {}).get("start") is not None
            )
            if speaking:
                voiced = True

        chunk_ms = round(len(chunk) / SAMPLE_RATE * 1000)

        if not voiced:
            # A lone spike is noise (a cough, a door) and must not hold the
            # buffer open. But once enough voiced audio has accumulated to look
            # like real speech, tolerate a short gap: the VAD flickers around
            # its threshold and natural speech onset has micro-pauses, so
            # resetting on the first quiet frame made follow-up fail
            # intermittently.
            speech_like = self._followup_voiced_ms >= _FOLLOWUP_MIN_SPEECH_MS
            self._followup_silence_ms += chunk_ms
            if not speech_like or self._followup_silence_ms >= _FOLLOWUP_GAP_TOLERANCE_MS:
                self._followup_buffer = []
                self._followup_voiced_ms = 0
                self._followup_silence_ms = 0
            else:
                # Keep the gap in the buffer so the pre-roll stays contiguous.
                self._followup_buffer.append(chunk)
            return

        if self._followup_voiced_ms == 0:
            # First voiced frame of a candidate follow-up. Logged so a failure
            # to engage can be told apart from the mic never hearing anything.
            logger.info(
                "Follow-up speech starting (need %d ms sustained)",
                self._followup_activation_ms,
            )
        self._followup_silence_ms = 0
        self._followup_buffer.append(chunk)
        self._followup_voiced_ms += chunk_ms
        if self._followup_voiced_ms >= self._followup_activation_ms:
            logger.info("Sustained follow-up speech detected, continuing conversation")
            pre_roll = list(self._followup_buffer)
            self._followup_armed = False
            self._enter_listening()
            self._speech_buffer = pre_roll
            self._speech_started_at = time.monotonic()
            self._last_voice_at = self._speech_started_at

    # -- Speech processing --

    def _process_speech(self) -> None:
        """Transcribe accumulated audio and publish to the message bus."""
        if not self._speech_buffer:
            self._state = PipelineState.IDLE
            return

        raw_audio = np.concatenate(self._speech_buffer)
        float_audio = raw_audio.astype(np.float32) / 32768.0
        self._speech_buffer = []

        # Voice ID: drop the utterance if it isn't the enrolled owner (so other
        # people talking can't drive the assistant). Verify the original signal;
        # denoising can alter the speaker characteristics used by embeddings.
        if self._speaker is not None and not self._speaker.verify(float_audio):
            logger.info("Utterance rejected by speaker verification")
            self._events.emit_speaker(verified=False)
            self._state = PipelineState.IDLE
            return
        if self._speaker is not None:
            self._events.emit_speaker(verified=True)

        if self._denoise:
            float_audio = self._denoise_audio(float_audio)

        try:
            text, detected_lang = self._stt.transcribe(
                float_audio, context=" ".join(self._recent_turns)
            )
        except STTError:
            logger.exception("STT failed")
            self._state = PipelineState.IDLE
            return

        if not text.strip():
            logger.info("No speech detected in audio buffer")
            self._state = PipelineState.IDLE
            return

        logger.info("Transcribed (%s): %s", detected_lang, text)
        self._events.emit_transcript(text, detected_lang, final=True)
        language = self._map_language(detected_lang)
        self._last_language = language
        self._last_user_text = text
        self._recent_turns.append(text)

        self._turn += 1
        # Ensure a conversation scope exists (defensive — wake sets it) and
        # mark the session live so it does not expire mid-conversation.
        if self._conversation_id is None:
            self._resume_or_start_session()
        self._session_last_activity = time.monotonic()
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
                self._voice_channel.drain(),
                self._loop,
            ).result(timeout=2)
        except Exception:
            logger.debug("Voice queue drain failed", exc_info=True)

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._bus.publish_inbound(message),
                self._loop,
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
            self._response_future = future
            response: Message | None = future.result(timeout=self._response_timeout + 10)

            if response is None:
                logger.warning("Timed out waiting for assistant response")
                self._state = PipelineState.IDLE
                return

            logger.info("Speaking response: %.80s...", response.content)
            self._last_reply_was_question = _ends_with_question(response.content)
            # Dax's own reply carries the entity names the user is most likely
            # to echo back ("la luz del cuarto"), so it biases the next turn too.
            self._recent_turns.append(_clean_for_speech(response.content))

            tts_lang = "en"
            if language == Language.SPANISH or response.language == Language.SPANISH:
                tts_lang = "es"

            remote_turn = self._output_owner is not None
            interrupted = self._speak(response.content, tts_lang)
            # Restart the inactivity clock from the end of the reply, not from
            # when the turn was published — a slow tool call must not eat into
            # the session's idle budget.
            self._session_last_activity = time.monotonic()

            # One line that names the branch about to be taken. Without it the
            # log simply stops after "Speaking response" and every diagnosis of
            # "follow-up did not engage" is guesswork.
            logger.info(
                "Reply spoken — interrupted=%s question=%s farewell=%s require_wake_each_turn=%s",
                interrupted,
                self._last_reply_was_question,
                self._is_farewell(self._last_user_text),
                self._require_wake_each_turn,
            )

            if interrupted:
                logger.info("Barge-in detected — listening to the user")
                self._enter_barge_in_listening()
                return

            # End the conversation only when the USER said goodbye — not when
            # Dax's reply happens to contain filler like "listo".
            if self._is_farewell(self._last_user_text):
                logger.info("Farewell detected, ending conversation")
                # An explicit goodbye is the one reliable signal that the user
                # is done — drop the session so the next wake word starts clean.
                self._end_session()
                self._state = PipelineState.IDLE
            elif self._output_owner is not None:
                # Remote follow-up is client-driven. Entering CONVERSING here
                # would silently switch input to the backend host microphone.
                logger.info("Remote reply complete — returning to IDLE for client follow-up")
                self._state = PipelineState.IDLE
            elif self._require_wake_each_turn or not self._followup_armed:
                # No hands-free follow-up: wait for the wake word again. Logged
                # because a silent exit here is indistinguishable from a broken
                # follow-up — this branch hid a config problem for three
                # debugging rounds.
                logger.info(
                    "Automatic follow-up unavailable — returning to IDLE"
                )
                self._state = PipelineState.IDLE
            else:
                self._enter_conversing()

            if remote_turn:
                # Completion is the client's permission to release its lease.
                # Emit it only after the state is IDLE, never while SPEAKING.
                self._events.emit_turn_completed(str(self._turn))

        except TTSError:
            logger.exception("TTS synthesis failed")
            self._state = PipelineState.IDLE
        except Exception:
            logger.exception("Error during speech playback")
            self._state = PipelineState.IDLE
        finally:
            self._response_future = None

    def _speak(self, text: str, tts_lang: str) -> bool:
        """Synthesise and play *text*. Returns True if interrupted (barge-in)."""
        sentences = _split_sentences(_clean_for_speech(text))

        if self._output_owner is not None:
            # A remote client owns output. Publish the sentences it should
            # speak and do no local work: no synthesis, no playback, and no
            # mic muting, because the microphone in question is not ours.
            # Barge-in is the client's to detect for the same reason.
            for sentence in sentences:
                self._events.emit_speech(sentence, tts_lang)
            return False

        if not self._barge_in:
            # Mute the mic during playback to prevent echo/feedback.
            self._capture.stop()
            self._drain_mic_buffer()
            try:
                for sentence in sentences:
                    result = self._tts.synthesize(sentence, language=tts_lang)
                    self._events.emit_speech(sentence, tts_lang)
                    self._player.play(result.audio, sample_rate=result.sample_rate)
            finally:
                time.sleep(0.3)
                self._capture.start()
            return False

        # Barge-in: keep the mic live and let the wake word interrupt playback.
        self._drain_mic_buffer()
        self._wakeword.reset()
        interrupted = False
        for sentence in sentences:
            result = self._tts.synthesize(sentence, language=tts_lang)
            self._events.emit_speech(sentence, tts_lang)
            interrupted = self._player.play_blocks(
                result.audio,
                sample_rate=result.sample_rate,
                should_stop=self._bargein_detected,
                on_block=self._emit_output_level,
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

    def _enter_barge_in_listening(self) -> None:
        """Listen immediately without discarding speech after the wake word.

        The detector has already consumed the wake-word frames. Any following
        command is still queued by the live microphone and must survive the
        transition; draining here used to cut off fast "Hey Dax, para" turns.
        """
        self._enter_listening()

    # -- Spoken confirmation (voice approval) --

    async def _voice_approve(
        self,
        *,
        approval_id: str,
        tool_name: str,
        server_name: str | None = None,
        arguments: dict[str, object] | None = None,
        options: list[str] | None = None,
        timeout_seconds: int = 120,
    ) -> str | None:
        """Ask the user to confirm a tool by voice; return the decision.

        Runs the blocking speak+listen cycle in a worker thread so the event
        loop (and the rest of the agent) isn't stalled. Called by the
        ApprovalManager when a gated tool originates from the voice channel.
        """
        if self._output_owner is not None:
            self._events.emit_approval_request(
                approval_id=approval_id,
                tool_name=tool_name,
                server_name=server_name or "",
                arguments=dict(arguments or {}),
                options=options or ["approve"],
                timeout_seconds=timeout_seconds,
            )
            return None
        return await self._loop.run_in_executor(
            None,
            self._confirm_blocking,
            tool_name,
            options or [],
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
        if self._output_owner is not None:
            # Spoken confirmations have to reach the person who is actually
            # being asked. Publishing lets the owning client speak it; playing
            # here would ask an empty room and then time out into a denial.
            self._events.emit_speech(text, lang)
            return
        self._capture.stop()
        self._drain_mic_buffer()
        try:
            result = self._tts.synthesize(text, language=lang)
            self._player.play(result.audio, sample_rate=result.sample_rate)
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
            chunk = self._read_metered_chunk(timeout=0.5)
            if chunk is None:
                continue
            chunks.append(chunk)
            float_chunk = chunk.astype(np.float32) / 32768.0
            voiced = False
            for offset in range(0, len(float_chunk), VAD_CHUNK_SIZE):
                sub = float_chunk[offset : offset + VAD_CHUNK_SIZE]
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
            "sí",
            "si",
            "claro",
            "dale",
            "hazlo",
            "ok",
            "okay",
            "vale",
            "adelante",
            "confirmo",
            "confirmar",
            "yes",
            "yeah",
            "yep",
            "sure",
            "go ahead",
            "do it",
            "confirm",
            "affirmative",
        }
        no = {
            "no",
            "nop",
            "negativo",
            "cancela",
            "cancelar",
            "para",
            "detente",
            "nope",
            "cancel",
            "stop",
            "don't",
            "negative",
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

    # -- Session scope --

    def _resume_or_start_session(self) -> None:
        """Resume the current voice session, or start a fresh one if it expired.

        The session id becomes ``metadata["session_id"]``, which the agent uses
        as its conversation key — so this single decision is what gives voice
        turns memory of each other. Resuming is the common case: consecutive
        commands ("pon la luz en amarillo" → "ponla de color rojo") must share
        history, and the follow-up window is far too short to rely on.

        A session expires only after :attr:`_session_ttl_s` of real inactivity,
        which is the point at which the user has almost certainly moved on and
        stale context would hurt more than help.
        """
        now = time.monotonic()
        idle_for = now - self._session_last_activity

        current = self._conversation_id
        expired = current is None or self._session_ttl_s <= 0 or idle_for > self._session_ttl_s
        if expired:
            self._conversation_id = uuid.uuid4().hex
            self._recent_turns.clear()
            self._last_reply_was_question = False
            logger.info(
                "Starting new voice session %s (idle for %.0fs)",
                self._conversation_id[:8],
                idle_for if self._session_last_activity else 0.0,
            )
        else:
            logger.info(
                "Resuming voice session %s (idle for %.0fs)",
                current[:8] if current else "?",
                idle_for,
            )
        self._session_last_activity = now

    def _end_session(self) -> None:
        """Forget the current session so the next wake word starts clean.

        Called on an explicit farewell — the one signal that the user really is
        done, as opposed to merely pausing.
        """
        self._reset_conversation_context()
        logger.info("Voice session ended")

    def _reset_conversation_context(self) -> None:
        """Drop all conversational state at an input/output ownership boundary."""
        self._conversation_id = None
        self._session_last_activity = 0.0
        self._recent_turns.clear()
        self._last_reply_was_question = False
        self._last_user_text = ""
        self._last_language = Language.AUTO
        self._followup_armed = False
        self._followup_buffer = []
        self._followup_voiced_ms = 0
        self._followup_silence_ms = 0

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
        self._followup_buffer = []
        self._followup_voiced_ms = 0
        self._followup_silence_ms = 0
        self._drain_mic_buffer()  # discard any TTS tail before listening
        logger.info(
            "Conversation mode — listening for follow-up (%ds timeout, question=%s)",
            self._conv_timeout_question if self._last_reply_was_question else self._conv_timeout,
            self._last_reply_was_question,
        )

    # -- Earcons --

    def _play_earcon(self, kind: str = "wake") -> None:
        """Play a short confirmation tone with the mic muted.

        A wake earcon gives instant feedback (Alexa-style) the moment the wake
        word fires, so the user knows to start speaking. Best-effort: any audio
        error is swallowed so it never blocks the conversation.
        """
        if self._output_owner is not None:
            # The owning client plays its own earcon next to the user's ear;
            # one here would only be audible to the backend host.
            return
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

    def _read_metered_chunk(self, timeout: float = 0.5) -> np.ndarray | None:
        """Read a mic chunk and broadcast its level to any UI clients.

        Wraps every capture read that can contain the user's voice, so the
        waveform stays live across IDLE, LISTENING and CONVERSING without each
        state handler having to remember to publish. Metering is skipped
        entirely when nobody is subscribed.
        """
        with self._source_lock:
            source = self._audio_source
        chunk = source.read_chunk(timeout=timeout)
        if chunk is not None:
            emit_level(self._events, chunk, LevelSource.INPUT)
        return chunk

    def _emit_output_level(self, block: np.ndarray) -> None:
        """Broadcast the level of a TTS playback block as it reaches the speaker.

        Lets the UI show Dax's own voice as a waveform, visually distinct from
        the user's, rather than freezing while he speaks.
        """
        emit_level(self._events, block, LevelSource.OUTPUT)

    def _drain_mic_buffer(self) -> None:
        """Discard any buffered audio chunks from the mic queue."""
        with self._source_lock:
            source = self._audio_source
        while source.read_chunk(timeout=0.01) is not None:
            pass

    def _drain_remote_ptt_tail(self) -> None:
        """Move accepted remote frames into the utterance before PTT stops."""
        with self._source_lock:
            source = self._audio_source
        if source is self._capture:
            return
        while True:
            chunk = source.read_chunk(timeout=0.0)
            if chunk is None:
                return
            self._speech_buffer.append(chunk)
            emit_level(self._events, chunk, LevelSource.INPUT)

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
            "chao",
            "chau",
            "adiós",
            "adios",
            "hasta luego",
            "hasta pronto",
            "nos vemos",
            "buenas noches",
            # English
            "bye",
            "goodbye",
            "good bye",
            "see you",
            "see ya",
            "take care",
            "good night",
            "that's all",
            "thats all",
            # Polite closers (user-side only; "listo" removed — Dax says it
            # constantly as filler and it must not end the conversation).
            "gracias",
            "thanks",
            "thank you",
            "eso es todo",
        }
        lower = text.lower().strip()
        # Check if the response is short AND contains a farewell
        if len(lower.split()) > 15:
            return False
        return any(pattern in lower for pattern in farewell_patterns)
