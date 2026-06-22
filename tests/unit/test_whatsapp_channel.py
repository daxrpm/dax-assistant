"""Tests for the WhatsApp outbound channel."""

from __future__ import annotations

import pytest

from dax.channels.whatsapp_channel import WhatsAppChannel
from dax.core.config import WhatsAppConfig
from dax.core.exceptions import ChannelError
from dax.core.models import ChannelType, Message, MessageRole


class TestWhatsAppChannel:
    def test_name(self):
        config = WhatsAppConfig(
            enabled=True,
            evolution_api_url="http://localhost:8080",
            evolution_api_instance="test",
            evolution_api_key="key",
        )
        channel = WhatsAppChannel(config)
        assert channel.name == "whatsapp"

    async def test_send_without_start_raises(self):
        config = WhatsAppConfig(
            enabled=True,
            evolution_api_url="http://localhost:8080",
            evolution_api_instance="test",
            evolution_api_key="key",
        )
        channel = WhatsAppChannel(config)

        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Hello",
            channel=ChannelType.WHATSAPP,
            metadata={"sender_jid": "123@s.whatsapp.net"},
        )

        with pytest.raises(ChannelError, match="not started"):
            await channel.send(msg)

    async def test_send_without_sender_jid_skips(self):
        config = WhatsAppConfig(
            enabled=True,
            evolution_api_url="http://localhost:8080",
            evolution_api_instance="test",
            evolution_api_key="key",
        )
        channel = WhatsAppChannel(config)
        await channel.start()

        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Hello",
            channel=ChannelType.WHATSAPP,
            metadata={},  # No sender_jid
        )

        # Should not raise, just warn and skip
        await channel.send(msg)
        await channel.stop()
