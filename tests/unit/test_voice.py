"""Tests for voice pipeline components.

These tests mock hardware dependencies (microphone, speaker) and ML models
to verify the pipeline logic without requiring audio hardware or model files.
"""

from __future__ import annotations

import asyncio
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
            patch("dax.voice.pipeline.SpeechToText"),
            patch("dax.voice.pipeline.TextToSpeech"),
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
