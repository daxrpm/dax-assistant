"""Tests for voice pipeline components.

These tests mock hardware dependencies (microphone, speaker) and ML models
to verify the pipeline logic without requiring audio hardware or model files.
"""

from __future__ import annotations

import asyncio
import io
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from dax.channels.voice_channel import VoiceChannel
from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.voice.audio_io import AudioCapture, AudioPlayer
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
            patch("dax.voice.pipeline.build_tts"),
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

        payload = OpenAISpeechToText._wav_bytes(
            np.array([-1.0, 0.0, 1.0], dtype=np.float32)
        )
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
        assert isinstance(
            build_stt(VoiceConfig(stt_backend="openai")), FallbackSpeechToText
        )
        assert isinstance(
            build_stt(VoiceConfig(
                stt_backend="openai", stt_fallback_to_local=False
            )),
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


class TestSpeakerVerifier:
    """Voice ID must fail open when no profile/encoder is available."""

    def test_fails_open_without_profile(self, tmp_path):
        from dax.voice.speaker import SpeakerVerifier

        verifier = SpeakerVerifier(profile_path=str(tmp_path / "p.npy"))
        # No encoder loaded and no profile → accept everything.
        assert verifier.active is False
        assert verifier.verify(np.zeros(16000, dtype=np.float32)) is True
