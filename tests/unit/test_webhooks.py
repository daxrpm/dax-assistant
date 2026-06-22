"""Tests for Evolution API v2 webhook receiver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from dax.core.config import DaxConfig
from dax.core.models import ChannelType
from dax.orchestrator.bus import MessageBus
from dax.web.server import create_app

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def bus() -> MessageBus:
    b = MessageBus()
    b.start()
    return b


@pytest.fixture
def app(bus: MessageBus) -> FastAPI:
    config = DaxConfig()
    fastapi_app = create_app(config=config, bus=bus)
    fastapi_app.state.config = config
    fastapi_app.state.bus = bus
    fastapi_app.state.voice_listening = config.voice.enabled
    return fastapi_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


def _make_text_webhook(text: str, sender: str = "5531982968011@s.whatsapp.net") -> dict:
    """Build a realistic Evolution API v2 text message webhook payload."""
    return {
        "event": "messages.upsert",
        "instance": "dax",
        "data": {
            "key": {
                "remoteJid": sender,
                "fromMe": False,
                "id": "BAE594145F4C59B4",
            },
            "pushName": "Test User",
            "message": {
                "conversation": text,
            },
            "messageType": "conversation",
            "messageTimestamp": 1742425200,
            "instanceId": "clxyz123",
            "source": "android",
        },
        "date_time": "2026-03-19T12:00:00-03:00",
        "sender": sender,
        "server_url": "http://localhost:8080",
        "apikey": "test-api-key",
    }


def _make_extended_text_webhook(text: str) -> dict:
    """Build a webhook with extendedTextMessage type."""
    return {
        "event": "messages.upsert",
        "instance": "dax",
        "data": {
            "key": {
                "remoteJid": "5531982968011@s.whatsapp.net",
                "fromMe": False,
                "id": "BAE594145F4C59B5",
            },
            "pushName": "Test User",
            "message": {
                "extendedTextMessage": {
                    "text": text,
                    "matchedText": "https://example.com",
                },
            },
            "messageType": "extendedTextMessage",
            "messageTimestamp": 1742425200,
        },
        "date_time": "2026-03-19T12:00:00-03:00",
        "sender": "5531982968011@s.whatsapp.net",
    }


def _make_audio_webhook(seconds: int = 5) -> dict:
    """Build a webhook with audioMessage type."""
    return {
        "event": "messages.upsert",
        "instance": "dax",
        "data": {
            "key": {
                "remoteJid": "5531982968011@s.whatsapp.net",
                "fromMe": False,
                "id": "3EB0A0C1D2E3F4A5",
            },
            "pushName": "Test User",
            "message": {
                "audioMessage": {
                    "mimetype": "audio/ogg; codecs=opus",
                    "seconds": seconds,
                    "ptt": True,
                },
            },
            "messageType": "audioMessage",
            "messageTimestamp": 1742425200,
        },
        "date_time": "2026-03-19T12:00:00-03:00",
        "sender": "5531982968011@s.whatsapp.net",
    }


class TestWhatsAppWebhook:
    async def test_text_message(self, client: AsyncClient, bus: MessageBus):
        """Text messages should be published to the inbound bus."""
        payload = _make_text_webhook("Hello Dax!")

        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200

        assert bus.inbound_pending == 1
        msg = await bus.consume_inbound()
        assert msg.content == "Hello Dax!"
        assert msg.channel == ChannelType.WHATSAPP
        assert msg.metadata["sender_jid"] == "5531982968011@s.whatsapp.net"
        assert msg.metadata["sender_name"] == "Test User"

    async def test_extended_text_message(self, client: AsyncClient, bus: MessageBus):
        """Extended text messages (with URL preview) should extract text."""
        payload = _make_extended_text_webhook("Check out https://example.com")

        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200

        msg = await bus.consume_inbound()
        assert msg.content == "Check out https://example.com"

    async def test_audio_message(self, client: AsyncClient, bus: MessageBus):
        """Audio messages should be queued with metadata."""
        payload = _make_audio_webhook(seconds=10)

        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200

        msg = await bus.consume_inbound()
        assert "Audio message" in msg.content
        assert msg.metadata["audio_seconds"] == 10
        assert msg.metadata["message_type"] == "audio"

    async def test_outgoing_message_ignored(self, client: AsyncClient, bus: MessageBus):
        """Messages sent by us (fromMe=True) should be ignored."""
        payload = _make_text_webhook("Sent by me")
        payload["data"]["key"]["fromMe"] = True

        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200
        assert bus.inbound_pending == 0

    async def test_non_message_event_ignored(self, client: AsyncClient, bus: MessageBus):
        """Non-message events should be acknowledged but not processed."""
        payload = {
            "event": "connection.update",
            "instance": "dax",
            "data": {"state": "open"},
        }

        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200
        assert bus.inbound_pending == 0

    async def test_unsupported_message_type_ignored(self, client: AsyncClient, bus: MessageBus):
        """Unsupported message types (sticker, location, etc.) should be ignored."""
        payload = {
            "event": "messages.upsert",
            "instance": "dax",
            "data": {
                "key": {
                    "remoteJid": "5531982968011@s.whatsapp.net",
                    "fromMe": False,
                    "id": "test123",
                },
                "pushName": "Test",
                "message": {"stickerMessage": {}},
                "messageType": "stickerMessage",
                "messageTimestamp": 1742425200,
            },
        }

        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200
        assert bus.inbound_pending == 0

    async def test_sender_metadata_preserved(self, client: AsyncClient, bus: MessageBus):
        """Sender JID and name should be in message metadata for reply routing."""
        payload = _make_text_webhook(
            "Hi", sender="5599887766555@s.whatsapp.net"
        )
        payload["data"]["pushName"] = "Maria"

        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200

        msg = await bus.consume_inbound()
        assert msg.metadata["sender_jid"] == "5599887766555@s.whatsapp.net"
        assert msg.metadata["sender_name"] == "Maria"
        assert msg.metadata["instance"] == "dax"


@pytest.fixture
def secured_app(bus: MessageBus) -> FastAPI:
    config = DaxConfig(whatsapp={"webhook_secret": "s3cr3t"})
    app = create_app(config=config, bus=bus)
    app.state.config = config
    app.state.bus = bus
    app.state.voice_listening = config.voice.enabled
    return app


@pytest.fixture
async def secured_client(secured_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=secured_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


class TestWebhookSecret:
    async def test_missing_secret_rejected(
        self, secured_client: AsyncClient, bus: MessageBus
    ):
        resp = await secured_client.post(
            "/webhook/whatsapp", json=_make_text_webhook("hi")
        )
        assert resp.status_code == 401
        assert bus.inbound_pending == 0

    async def test_wrong_secret_rejected(
        self, secured_client: AsyncClient, bus: MessageBus
    ):
        resp = await secured_client.post(
            "/webhook/whatsapp",
            json=_make_text_webhook("hi"),
            headers={"apikey": "wrong"},
        )
        assert resp.status_code == 401
        assert bus.inbound_pending == 0

    async def test_correct_secret_accepted(
        self, secured_client: AsyncClient, bus: MessageBus
    ):
        resp = await secured_client.post(
            "/webhook/whatsapp",
            json=_make_text_webhook("hi"),
            headers={"apikey": "s3cr3t"},
        )
        assert resp.status_code == 200
        assert bus.inbound_pending == 1
