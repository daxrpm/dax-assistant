"""Tests for voice pipeline components.

These tests mock hardware dependencies (microphone, speaker) and ML models
to verify the pipeline logic without requiring audio hardware or model files.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
import wave
from concurrent.futures import CancelledError as FutureCancelledError
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from dax.channels.voice_channel import VoiceChannel
from dax.core.exceptions import VoiceError
from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.voice.audio_io import AudioCapture, AudioPlayer, RemoteAudioSource
from dax.voice.pipeline import PipelineState, VoicePipeline


class TestVoiceChannel:
    async def test_send_queues_message(self):
        channel = VoiceChannel()
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Hello!",
            channel=ChannelType.VOICE,
        )
        await channel.send(msg)

        result = await channel.get_response(timeout=1.0)
        assert result is not None
        assert result.content == "Hello!"

    async def test_get_response_timeout(self):
        channel = VoiceChannel()
        result = await channel.get_response(timeout=0.1)
        assert result is None

    def test_name(self):
        channel = VoiceChannel()
        assert channel.name == "voice"


class TestAudioCapture:
    def test_init(self):
        capture = AudioCapture(sample_rate=16000, chunk_size=1280)
        assert capture._sample_rate == 16000
        assert capture._chunk_size == 1280

    def test_read_chunk_empty_returns_none(self):
        capture = AudioCapture()
        # Don't start — queue is empty
        result = capture.read_chunk(timeout=0.01)
        assert result is None

    def test_read_chunk_with_data(self):
        capture = AudioCapture()
        # Manually put data in the queue
        test_data = np.zeros(1280, dtype=np.int16)
        capture._queue.put(test_data)
        result = capture.read_chunk(timeout=1.0)
        assert result is not None
        assert len(result) == 1280


class TestRemoteAudioSource:
    def test_decodes_little_endian_pcm(self):
        source = RemoteAudioSource()
        source.start()
        source.feed_pcm(b"\x01\x00\xff\x7f\x00\x80")
        assert source.read_chunk(timeout=0.01).tolist() == [1, 32767, -32768]

    @pytest.mark.parametrize("frame", [b"", b"\x00", b"\x00" * 3202])
    def test_rejects_invalid_frames(self, frame: bytes):
        source = RemoteAudioSource()
        source.start()
        with pytest.raises(ValueError):
            source.feed_pcm(frame)

    def test_queue_is_bounded_and_non_blocking(self):
        source = RemoteAudioSource(max_frames=1)
        source.start()
        source.feed_pcm(b"\x00\x00")
        with pytest.raises(BufferError, match="full"):
            source.feed_pcm(b"\x00\x00")


class TestAudioPlayer:
    @patch("dax.voice.audio_io.sd")
    def test_play(self, mock_sd: MagicMock):
        player = AudioPlayer()
        audio = np.zeros(22050, dtype=np.int16)
        player.play(audio, sample_rate=22050)
        mock_sd.play.assert_called_once()
        mock_sd.wait.assert_called_once()


class TestPipelineState:
    def test_states_exist(self):
        assert PipelineState.IDLE == "idle"
        assert PipelineState.LISTENING == "listening"
        assert PipelineState.PROCESSING == "processing"
        assert PipelineState.SPEAKING == "speaking"


class TestPipelineMapLanguage:
    def test_spanish(self):
        assert VoicePipeline._map_language("es") == Language.SPANISH

    def test_english(self):
        assert VoicePipeline._map_language("en") == Language.ENGLISH

    def test_unknown(self):
        assert VoicePipeline._map_language("fr") == Language.AUTO

    def test_auto(self):
        assert VoicePipeline._map_language("auto") == Language.AUTO


class TestPipelineEnabled:
    def _make_pipeline(self) -> VoicePipeline:
        """Create a pipeline with all components mocked."""
        from dax.core.config import VoiceConfig
        from dax.orchestrator.bus import MessageBus

        config = VoiceConfig()
        bus = MessageBus()
        bus.start()
        voice_channel = VoiceChannel()
        loop = asyncio.new_event_loop()

        with (
            patch("dax.voice.pipeline.AudioCapture"),
            patch("dax.voice.pipeline.AudioPlayer"),
            patch("dax.voice.pipeline.WakeWordDetector"),
            patch("dax.voice.pipeline.VoiceActivityDetector"),
            patch("dax.voice.pipeline.build_stt"),
            patch("dax.voice.pipeline.TTSService"),
        ):
            pipeline = VoicePipeline(
                config=config,
                bus=bus,
                voice_channel=voice_channel,
                loop=loop,
            )

        loop.close()
        return pipeline

    def test_enabled_default(self):
        pipeline = self._make_pipeline()
        assert pipeline.enabled is True

    def test_toggle_enabled(self):
        pipeline = self._make_pipeline()
        pipeline.enabled = False
        assert pipeline.enabled is False
        pipeline.enabled = True
        assert pipeline.enabled is True

    def test_initial_state_is_idle(self):
        pipeline = self._make_pipeline()
        assert pipeline.state == PipelineState.IDLE

    def test_pipeline_switches_to_pluggable_source_and_back(self):
        pipeline = self._make_pipeline()
        remote = RemoteAudioSource()
        pipeline.select_audio_source(remote)
        assert pipeline._audio_source is remote
        pipeline.select_audio_source(None)
        assert pipeline._audio_source is pipeline._capture

    def test_pipeline_refuses_source_switch_during_capture(self):
        pipeline = self._make_pipeline()
        pipeline._ptt_active = True
        with pytest.raises(VoiceError, match="Cannot switch"):
            pipeline.select_audio_source(RemoteAudioSource())

    def test_barge_in_preserves_queued_command_audio(self):
        pipeline = self._make_pipeline()
        pipeline._drain_mic_buffer = MagicMock()

        pipeline._enter_barge_in_listening()

        assert pipeline.state == PipelineState.LISTENING
        pipeline._drain_mic_buffer.assert_not_called()

    def test_speech_text_is_emitted_after_synthesis_before_playback(self):
        pipeline = self._make_pipeline()
        pipeline._barge_in = False
        pipeline._events = MagicMock()
        pipeline._capture.read_chunk.return_value = None
        pipeline._tts.synthesize.return_value = SimpleNamespace(
            audio=np.zeros(20, dtype=np.int16), sample_rate=24_000
        )
        order: list[str] = []
        pipeline._tts.synthesize.side_effect = lambda *_args, **_kwargs: (
            order.append("synthesize")
            or SimpleNamespace(audio=np.zeros(20, dtype=np.int16), sample_rate=24_000)
        )
        pipeline._events.emit_speech.side_effect = lambda *_args: order.append("speech")
        pipeline._player.play.side_effect = lambda *_args, **_kwargs: order.append("play")

        text = "Esta primera frase tiene suficiente longitud para mantenerse sola. Segunda frase."
        assert pipeline._speak(text, "es") is False

        assert order == ["synthesize", "speech", "play"] * 2
        assert pipeline._events.emit_speech.call_args_list[0].args == (
            "Esta primera frase tiene suficiente longitud para mantenerse sola.",
            "es",
        )

    def test_client_text_speak_emits_every_sentence_without_host_audio(self):
        pipeline = self._make_pipeline()
        pipeline._events = MagicMock()
        pipeline._output_owner = "mobile"
        pipeline._turn = 4

        pipeline._speak(
            "Esta primera frase tiene suficiente longitud para mantenerse sola. Segunda frase.",
            "es",
        )

        calls = pipeline._events.method_calls
        assert [call[0] for call in calls] == [
            "emit_speech",
            "emit_speech",
        ]
        pipeline._tts.synthesize.assert_not_called()

    def test_wake_node_speaks_each_sentence_on_its_origin(self):
        pipeline = self._make_pipeline()
        pipeline._events = MagicMock()
        pipeline._output_owner = "node"
        pipeline._wake_holder = "node"
        spoken: list[tuple[str, str, str]] = []

        async def speak(owner: str, text: str, language: str) -> None:
            spoken.append((owner, text, language))

        pipeline.set_remote_wake_speaker(speak)
        pipeline._loop = asyncio.new_event_loop()
        thread = threading.Thread(target=pipeline._loop.run_forever)
        thread.start()
        try:
            pipeline._speak(
                "Esta primera frase tiene suficiente longitud para mantenerse sola. "
                "Segunda frase.",
                "es",
            )
        finally:
            pipeline._loop.call_soon_threadsafe(pipeline._loop.stop)
            thread.join(timeout=1)
            pipeline._loop.close()

        assert spoken == [
            (
                "node",
                "Esta primera frase tiene suficiente longitud para mantenerse sola.",
                "es",
            ),
            ("node", "Segunda frase.", "es"),
        ]
        pipeline._tts.synthesize.assert_not_called()

    def test_remote_output_never_samples_host_microphone_while_idle(self):
        pipeline = self._make_pipeline()
        pipeline._output_owner = "mobile"

        pipeline._handle_idle()

        pipeline._capture.read_chunk.assert_not_called()

    def test_remote_lease_suppresses_host_input_and_output_and_restores_when_idle(self):
        pipeline = self._make_pipeline()
        generation = pipeline.acquire_remote_owner("mobile")

        pipeline._handle_idle()

        assert generation > 0
        assert pipeline.input_owner == "mobile"
        assert pipeline.output_owner == "mobile"
        pipeline._capture.read_chunk.assert_not_called()
        pipeline.release_remote_owner("mobile")
        assert pipeline.input_owner is None
        assert pipeline.output_owner is None
        assert pipeline._audio_source is pipeline._capture

    def test_remote_owner_generation_resets_conversation_and_followup_context(self):
        pipeline = self._make_pipeline()
        pipeline._resume_or_start_session()
        pipeline._recent_turns.extend(["local context"])
        pipeline._followup_armed = True
        pipeline._followup_buffer = [np.ones(10, dtype=np.int16)]
        local_session = pipeline._conversation_id

        pipeline.acquire_remote_owner("mobile")

        assert local_session is not None
        assert pipeline._conversation_id is None
        assert list(pipeline._recent_turns) == []
        assert pipeline._followup_armed is False
        assert pipeline._followup_buffer == []

        pipeline._resume_or_start_session()
        remote_session = pipeline._conversation_id
        pipeline._recent_turns.extend(["remote context"])
        pipeline.release_remote_owner("mobile")

        assert remote_session is not None
        assert pipeline._conversation_id is None
        assert list(pipeline._recent_turns) == []

    def test_remote_lease_cannot_be_released_before_idle(self):
        pipeline = self._make_pipeline()
        pipeline.acquire_remote_owner("mobile")
        pipeline._state = PipelineState.PROCESSING

        with pytest.raises(VoiceError, match="Cannot release"):
            pipeline.release_remote_owner("mobile")

        assert pipeline.input_owner == "mobile"

    async def test_remote_approval_emits_managed_request_without_host_microphone(self):
        pipeline = self._make_pipeline()
        pipeline._events = MagicMock()
        pipeline._output_owner = "mobile"
        pipeline._record_utterance = MagicMock()

        decision = await pipeline._voice_approve(
            approval_id="approval-1",
            tool_name="shell_run",
            server_name="dax-system",
            arguments={"command": "date"},
            options=["once", "save"],
            timeout_seconds=30,
        )

        assert decision is None
        pipeline._events.emit_approval_request.assert_called_once_with(
            approval_id="approval-1",
            tool_name="shell_run",
            server_name="dax-system",
            arguments={"command": "date"},
            options=["once", "save"],
            timeout_seconds=30,
        )
        pipeline._record_utterance.assert_not_called()
        pipeline._capture.read_chunk.assert_not_called()

    def test_remote_reply_returns_idle_instead_of_host_followup(self):
        pipeline = self._make_pipeline()
        pipeline._events = MagicMock()
        pipeline._output_owner = "mobile"
        pipeline._turn = 2
        pipeline._voice_channel.get_response = AsyncMock(
            return_value=Message(
                role=MessageRole.ASSISTANT,
                content="Respuesta remota.",
                channel=ChannelType.VOICE,
            )
        )
        pipeline._loop = asyncio.new_event_loop()
        thread = threading.Thread(target=pipeline._loop.run_forever)
        thread.start()
        try:
            pipeline._wait_and_speak(Language.SPANISH)
        finally:
            pipeline._loop.call_soon_threadsafe(pipeline._loop.stop)
            thread.join(timeout=1)
            pipeline._loop.close()

        assert pipeline.state == PipelineState.IDLE
        pipeline._events.emit_turn_completed.assert_called_once_with("2")
        pipeline._capture.read_chunk.assert_not_called()

    def test_followup_requires_sustained_speech(self):
        pipeline = self._make_pipeline()
        chunk = np.zeros(1280, dtype=np.int16)
        pipeline._capture.read_chunk.return_value = chunk
        pipeline._vad.speech_prob.return_value = 0.9
        pipeline._vad.threshold = 0.5
        pipeline._conversation_start = time.monotonic()
        pipeline._state = PipelineState.CONVERSING

        for _ in range(3):
            pipeline._handle_conversing()
            assert pipeline.state == PipelineState.CONVERSING

        pipeline._handle_conversing()
        assert pipeline.state == PipelineState.LISTENING
        assert len(pipeline._speech_buffer) == 4

    def test_followup_vad_spike_is_discarded(self):
        pipeline = self._make_pipeline()
        chunk = np.zeros(1280, dtype=np.int16)
        pipeline._capture.read_chunk.return_value = chunk
        pipeline._vad.speech_prob.side_effect = [0.9, 0.0, 0.0, 0.0, 0.0, 0.0]
        pipeline._vad.threshold = 0.5
        pipeline._conversation_start = time.monotonic()
        pipeline._state = PipelineState.CONVERSING

        pipeline._handle_conversing()
        pipeline._handle_conversing()

        assert pipeline.state == PipelineState.CONVERSING
        assert pipeline._followup_buffer == []


class TestYesNoParser:
    """The spoken-confirmation parser (voice approval)."""

    def test_spanish_yes(self):
        assert VoicePipeline._parse_yes_no("sí, claro", []) == "approve"

    def test_english_yes(self):
        assert VoicePipeline._parse_yes_no("yeah go ahead", []) == "approve"

    def test_no_denies(self):
        assert VoicePipeline._parse_yes_no("no, cancela", []) == "deny"

    def test_yes_maps_to_once_when_shell_option(self):
        assert VoicePipeline._parse_yes_no("dale", ["once", "save"]) == "once"

    def test_ambiguous_fails_safe_to_deny(self):
        assert VoicePipeline._parse_yes_no("mmm tal vez", []) == "deny"


class TestSTTLanguageResolution:
    """Auto-detect must never surface a spurious language (the 'ruso' bug)."""

    def _stt(self, language: str):
        from dax.voice.stt import SpeechToText

        return SpeechToText(language=language, fallback_language="es")

    def test_pinned_language_is_honoured(self):
        info = MagicMock(language="ru", language_probability=0.99)
        assert self._stt("es")._resolve_language(info) == "es"

    def test_low_confidence_falls_back(self):
        info = MagicMock(language="ru", language_probability=0.30)
        assert self._stt("auto")._resolve_language(info) == "es"

    def test_confident_english_accepted(self):
        info = MagicMock(language="en", language_probability=0.92)
        assert self._stt("auto")._resolve_language(info) == "en"


class TestOpenAIHostedSTT:
    def test_encodes_audio_as_16khz_mono_wav(self):
        from dax.voice.stt import OpenAISpeechToText

        payload = OpenAISpeechToText._wav_bytes(np.array([-1.0, 0.0, 1.0], dtype=np.float32))
        with wave.open(io.BytesIO(payload), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 16_000
            assert wav.getnframes() == 3

    def test_transcribes_with_model_language_and_prompt(self):
        from dax.voice.stt import OpenAISpeechToText

        stt = OpenAISpeechToText(
            model="gpt-4o-transcribe",
            language="es",
            prompt="Dax y Spotify",
        )
        stt._client = MagicMock()
        stt._client.audio.transcriptions.create.return_value = SimpleNamespace(
            text="Pon música en Spotify."
        )

        text, language = stt.transcribe(np.zeros(1600, dtype=np.float32))

        assert text == "Pon música en Spotify."
        assert language == "es"
        kwargs = stt._client.audio.transcriptions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-4o-transcribe"
        assert kwargs["language"] == "es"
        assert kwargs["prompt"] == "Dax y Spotify"
        assert kwargs["file"][0] == "speech.wav"

    def test_factory_selects_local_and_hosted_backends(self):
        from dax.core.config import VoiceConfig
        from dax.voice.stt import (
            FallbackSpeechToText,
            OpenAISpeechToText,
            SpeechToText,
            build_stt,
        )

        assert isinstance(build_stt(VoiceConfig(stt_backend="local")), SpeechToText)
        assert isinstance(build_stt(VoiceConfig(stt_backend="openai")), FallbackSpeechToText)
        assert isinstance(
            build_stt(VoiceConfig(stt_backend="openai", stt_fallback_to_local=False)),
            OpenAISpeechToText,
        )

    def test_hosted_failure_uses_lazy_local_fallback(self):
        from dax.core.exceptions import STTError
        from dax.voice.stt import FallbackSpeechToText

        primary = MagicMock()
        primary.transcribe.side_effect = STTError("network down")
        fallback = MagicMock()
        fallback.transcribe.return_value = ("hola", "es")
        stt = FallbackSpeechToText(primary, fallback)
        stt._primary_ready = True

        assert stt.transcribe(np.zeros(1600, dtype=np.float32)) == ("hola", "es")
        fallback.start.assert_called_once()


class TestBuildTTS:
    def test_piper_engine_returns_piper(self):
        from dax.core.config import VoiceConfig
        from dax.voice.tts import TextToSpeech, build_tts

        tts = build_tts(VoiceConfig(tts_engine="piper"), "models")
        assert isinstance(tts, TextToSpeech)

    def test_kokoro_engine_wraps_in_fallback(self):
        from dax.core.config import VoiceConfig
        from dax.voice.tts import _FallbackSynthesizer, build_tts

        tts = build_tts(VoiceConfig(tts_engine="kokoro"), "models")
        assert isinstance(tts, _FallbackSynthesizer)

    def test_openai_engine_wraps_in_local_fallback(self):
        from dax.core.config import VoiceConfig
        from dax.voice.tts import _FallbackSynthesizer, build_tts

        tts = build_tts(VoiceConfig(tts_engine="openai"), "models")
        assert isinstance(tts, _FallbackSynthesizer)

    def test_openai_tts_requests_pcm_with_spanish_instructions(self):
        from dax.voice.tts import OpenAITextToSpeech

        tts = OpenAITextToSpeech(voice="marin", instructions_es="Habla natural.")
        tts._client = MagicMock()
        tts._client.audio.speech.create.return_value = SimpleNamespace(
            content=np.array([0, 1000, -1000], dtype="<i2").tobytes()
        )

        audio = tts.synthesize("Hola", language="es")

        assert audio.tolist() == [0, 1000, -1000]
        kwargs = tts._client.audio.speech.create.call_args.kwargs
        assert kwargs["voice"] == "marin"
        assert kwargs["response_format"] == "pcm"
        assert kwargs["instructions"] == "Habla natural."


class TestTTSService:
    def test_serializes_synthesis_across_callers(self, monkeypatch):
        from dax.core.config import VoiceConfig
        from dax.voice.tts_service import TTSService

        class Engine:
            sample_rate = 24_000
            engine_name = "test"

            def __init__(self) -> None:
                self.active = 0
                self.max_active = 0

            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

            def synthesize(self, text: str, language: str = "en") -> np.ndarray:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                time.sleep(0.03)
                self.active -= 1
                return np.ones(10, dtype=np.int16)

            def voice_name(self, language: str) -> str | None:
                return "test-voice"

        engine = Engine()
        monkeypatch.setattr("dax.voice.tts_service.build_tts", lambda *_: engine)
        service = TTSService(VoiceConfig(), "models")
        barrier = threading.Barrier(3)

        def synthesize() -> None:
            barrier.wait()
            service.synthesize("hello", "en")

        workers = [threading.Thread(target=synthesize) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(timeout=1)

        assert all(not worker.is_alive() for worker in workers)
        assert engine.max_active == 1


class TestSpeakerVerifier:
    """Voice ID must fail open when no profile/encoder is available."""

    def test_fails_open_without_profile(self, tmp_path):
        from dax.voice.speaker import SpeakerVerifier

        verifier = SpeakerVerifier(profile_path=str(tmp_path / "p.npy"))
        # No encoder loaded and no profile → accept everything.
        assert verifier.active is False
        assert verifier.verify(np.zeros(16000, dtype=np.float32)) is True

    def test_can_fail_closed_without_profile(self, tmp_path):
        from dax.voice.speaker import SpeakerVerifier

        verifier = SpeakerVerifier(profile_path=str(tmp_path / "missing.npy"), fail_open=False)
        assert verifier.verify(np.zeros(16000, dtype=np.float32)) is False


class TestVoiceSession:
    """Session scoping — what gives consecutive voice turns shared memory.

    The session id becomes ``metadata["session_id"]``, which the agent uses as
    its conversation key. Minting a fresh one per wake word (the old behaviour)
    meant every activation loaded an empty history, so "ponla de color rojo"
    could not resolve what "la" referred to.
    """

    def _make_pipeline(self, **overrides) -> VoicePipeline:
        from dax.core.config import VoiceConfig
        from dax.orchestrator.bus import MessageBus

        config = VoiceConfig(**overrides)
        bus = MessageBus()
        bus.start()
        loop = asyncio.new_event_loop()

        with (
            patch("dax.voice.pipeline.AudioCapture"),
            patch("dax.voice.pipeline.AudioPlayer"),
            patch("dax.voice.pipeline.WakeWordDetector"),
            patch("dax.voice.pipeline.VoiceActivityDetector"),
            patch("dax.voice.pipeline.build_stt"),
            patch("dax.voice.pipeline.TTSService"),
        ):
            pipeline = VoicePipeline(
                config=config,
                bus=bus,
                voice_channel=VoiceChannel(),
                loop=loop,
            )

        loop.close()
        return pipeline

    def test_second_activation_resumes_same_session(self):
        """Back-to-back wake words must share one conversation."""
        pipeline = self._make_pipeline(session_ttl_minutes=10)

        pipeline._resume_or_start_session()
        first = pipeline._conversation_id
        pipeline._resume_or_start_session()

        assert first is not None
        assert pipeline._conversation_id == first

    def test_session_expires_after_ttl(self):
        """Once the user has been away long enough, context is dropped."""
        pipeline = self._make_pipeline(session_ttl_minutes=10)

        pipeline._resume_or_start_session()
        first = pipeline._conversation_id
        # Backdate the last activity past the TTL.
        pipeline._session_last_activity -= 601

        pipeline._resume_or_start_session()

        assert pipeline._conversation_id != first


    def test_state_event_uses_configured_session_expiration(self):
        pipeline = self._make_pipeline(session_ttl_minutes=10)
        pipeline._resume_or_start_session()

        with (
            patch("dax.voice.pipeline.time.monotonic", return_value=1000.0),
            patch("dax.voice.pipeline.time.time", return_value=1_800_000_000.0),
        ):
            pipeline._session_last_activity = 970.0
            pipeline._state = PipelineState.LISTENING

        event = pipeline.events.last_state
        assert event is not None
        assert event.data["session_expires_at"] == 1_800_000_570.0

    def test_ttl_zero_restores_per_activation_reset(self):
        """session_ttl_minutes=0 opts back into a fresh session every time."""
        pipeline = self._make_pipeline(session_ttl_minutes=0)

        pipeline._resume_or_start_session()
        first = pipeline._conversation_id
        pipeline._resume_or_start_session()

        assert pipeline._conversation_id != first

    def test_farewell_ends_session(self):
        """An explicit goodbye drops context immediately, without waiting."""
        pipeline = self._make_pipeline(session_ttl_minutes=10)

        pipeline._resume_or_start_session()
        assert pipeline._conversation_id is not None

        pipeline._end_session()

        assert pipeline._conversation_id is None

    def test_new_session_after_farewell(self):
        pipeline = self._make_pipeline(session_ttl_minutes=10)

        pipeline._resume_or_start_session()
        first = pipeline._conversation_id
        pipeline._end_session()
        pipeline._resume_or_start_session()

        assert pipeline._conversation_id != first


class TestPushToTalk:
    def _make_pipeline(self) -> VoicePipeline:
        from dax.core.config import VoiceConfig
        from dax.orchestrator.bus import MessageBus

        bus = MessageBus()
        bus.start()
        loop = asyncio.new_event_loop()
        with (
            patch("dax.voice.pipeline.AudioCapture"),
            patch("dax.voice.pipeline.AudioPlayer"),
            patch("dax.voice.pipeline.WakeWordDetector"),
            patch("dax.voice.pipeline.VoiceActivityDetector"),
            patch("dax.voice.pipeline.build_stt"),
            patch("dax.voice.pipeline.TTSService"),
        ):
            pipeline = VoicePipeline(VoiceConfig(), bus, VoiceChannel(), loop)
        pipeline._running = True
        loop.close()
        return pipeline

    @staticmethod
    def _request(pipeline: VoicePipeline, action: str) -> PipelineState:
        result: list[PipelineState] = []
        method = (
            pipeline.push_to_talk_press
            if action == "press"
            else pipeline.push_to_talk_release
        )
        worker = threading.Thread(target=lambda: result.append(method()))
        worker.start()
        while worker.is_alive():
            pipeline._drain_ptt_commands()
            worker.join(timeout=0.01)
        return result[0]

    def test_press_from_idle_starts_session_and_listening(self):
        pipeline = self._make_pipeline()

        state = self._request(pipeline, "press")

        assert state == PipelineState.LISTENING
        assert pipeline._ptt_active is True
        assert pipeline._conversation_id is not None

    def test_release_with_audio_processes_once(self):
        pipeline = self._make_pipeline()
        self._request(pipeline, "press")
        pipeline._speech_buffer = [np.ones(1280, dtype=np.int16)]
        pipeline._process_speech = MagicMock()  # type: ignore[method-assign]

        state = self._request(pipeline, "release")

        assert state == PipelineState.PROCESSING
        assert pipeline._ptt_active is False
        pipeline._process_speech.assert_called_once()

    def test_release_drains_all_accepted_remote_frames_before_processing(self):
        pipeline = self._make_pipeline()
        remote = RemoteAudioSource()
        remote.start()
        pipeline.select_audio_source(remote)
        self._request(pipeline, "press")
        remote.feed_pcm(b"\x01\x00" * 160)
        remote.feed_pcm(b"\x02\x00" * 160)
        captured: list[np.ndarray] = []
        pipeline._process_speech = lambda: captured.append(  # type: ignore[method-assign]
            np.concatenate(pipeline._speech_buffer)
        )

        assert self._request(pipeline, "release") == PipelineState.PROCESSING
        assert len(captured) == 1
        assert captured[0].tolist() == [1] * 160 + [2] * 160

    def test_release_without_audio_returns_idle_and_is_idempotent(self):
        pipeline = self._make_pipeline()
        self._request(pipeline, "press")

        assert self._request(pipeline, "release") == PipelineState.IDLE
        assert self._request(pipeline, "release") == PipelineState.IDLE

    def test_ptt_disables_automatic_endpointing_while_held(self):
        pipeline = self._make_pipeline()
        self._request(pipeline, "press")
        pipeline._capture.read_chunk.return_value = np.ones(1280, dtype=np.int16)
        pipeline._adaptive_endpoint = MagicMock(return_value=True)  # type: ignore[method-assign]

        pipeline._handle_listening()

        assert pipeline.state == PipelineState.LISTENING
        pipeline._adaptive_endpoint.assert_not_called()

    def test_interrupted_remote_response_is_not_a_playback_error(self, caplog):
        pipeline = self._make_pipeline()
        future = MagicMock()
        future.result.side_effect = FutureCancelledError()

        def submit(coroutine, _loop):
            coroutine.close()
            return future

        with patch("dax.voice.pipeline.asyncio.run_coroutine_threadsafe", submit):
            pipeline._wait_and_speak(Language.SPANISH)

        assert pipeline.state == PipelineState.IDLE
        assert "Error during speech playback" not in caplog.text

    def test_timed_out_command_cannot_run_late(self):
        pipeline = self._make_pipeline()

        with pytest.raises(VoiceError, match="did not accept"):
            pipeline.push_to_talk_press(timeout=0.001)
        pipeline._drain_ptt_commands()

        assert pipeline.state == PipelineState.IDLE
        assert pipeline._ptt_active is False


class TestFollowUpDetection:
    """Hands-free follow-up must survive the micro-pauses of real speech.

    The original rule required consecutive voiced frames and reset on the first
    quiet one, so natural speech onset intermittently failed to engage.
    """

    def _make_pipeline(self) -> VoicePipeline:
        from dax.core.config import VoiceConfig
        from dax.orchestrator.bus import MessageBus

        bus = MessageBus()
        bus.start()
        loop = asyncio.new_event_loop()

        with (
            patch("dax.voice.pipeline.AudioCapture"),
            patch("dax.voice.pipeline.AudioPlayer"),
            patch("dax.voice.pipeline.WakeWordDetector"),
            patch("dax.voice.pipeline.VoiceActivityDetector"),
            patch("dax.voice.pipeline.build_stt"),
            patch("dax.voice.pipeline.TTSService"),
        ):
            pipeline = VoicePipeline(
                config=VoiceConfig(),
                bus=bus,
                voice_channel=VoiceChannel(),
                loop=loop,
            )

        loop.close()
        return pipeline

    def _drive(self, pipeline: VoicePipeline, voiced_flags: list[bool]) -> None:
        """Feed one 80 ms chunk per flag, voiced or not."""
        chunk = np.zeros(1280, dtype=np.int16)
        pipeline._capture.read_chunk.return_value = chunk
        pipeline._vad.threshold = 0.5
        pipeline._conversation_start = time.monotonic()
        pipeline._state = PipelineState.CONVERSING

        for voiced in voiced_flags:
            pipeline._vad.speech_prob.return_value = 0.9 if voiced else 0.0
            pipeline._handle_conversing()

    def test_gap_mid_utterance_does_not_reset(self):
        """A brief dip below threshold must not discard accumulated speech."""
        pipeline = self._make_pipeline()

        # Two voiced chunks (160 ms, past the speech-like floor), one dip.
        self._drive(pipeline, [True, True, False])

        assert pipeline.state == PipelineState.CONVERSING
        assert pipeline._followup_voiced_ms == 160
        assert pipeline._followup_buffer != []

    def test_engages_across_a_gap(self):
        """Speech interrupted by a micro-pause still triggers follow-up."""
        pipeline = self._make_pipeline()

        self._drive(pipeline, [True, True, False, True, True])

        assert pipeline.state == PipelineState.LISTENING

    def test_long_silence_still_discards(self):
        """Past the tolerance the buffer is dropped, so noise cannot accrue."""
        pipeline = self._make_pipeline()

        # 160 ms voiced, then 400 ms of silence (5 chunks) exceeds tolerance.
        self._drive(pipeline, [True, True, False, False, False, False, False])

        assert pipeline.state == PipelineState.CONVERSING
        assert pipeline._followup_buffer == []
        assert pipeline._followup_voiced_ms == 0

    def test_automatic_followup_is_consumed_once(self):
        pipeline = self._make_pipeline()
        pipeline._followup_armed = True

        self._drive(pipeline, [True, True, True, True])

        assert pipeline.state == PipelineState.LISTENING
        assert pipeline._followup_armed is False

    def test_followup_silence_returns_idle(self):
        pipeline = self._make_pipeline()
        pipeline._conversation_start = time.monotonic() - pipeline._conv_timeout - 1
        pipeline._state = PipelineState.CONVERSING

        pipeline._handle_conversing()

        assert pipeline.state == PipelineState.IDLE
