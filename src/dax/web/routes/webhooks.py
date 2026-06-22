"""Evolution API v2 webhook receiver.

Handles incoming WhatsApp messages (text and audio) from Evolution API v2
and publishes them to the message bus for processing.

Webhook payload format (outer envelope):
{
    "event": "messages.upsert",
    "instance": "instance-name",
    "data": { ... message payload ... },
    "date_time": "2026-03-19T12:00:00-03:00",
    "sender": "5531982968011@s.whatsapp.net"
}
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from dax.core.models import ChannelType, Language, Message, MessageRole

router = APIRouter(tags=["webhooks"])

logger = logging.getLogger(__name__)


class WebhookEnvelope(BaseModel):
    """Evolution API v2 webhook outer envelope."""

    event: str
    instance: str
    data: dict[str, Any]
    date_time: str = ""
    sender: str = ""
    server_url: str = ""
    apikey: str = ""


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    payload: WebhookEnvelope,
) -> Response:
    """Receive and process WhatsApp messages from Evolution API v2.

    Handles:
    - Text messages (conversation, extendedTextMessage)
    - Audio messages (audioMessage) — queued for future STT processing

    All other event types are logged and acknowledged.
    """
    # Reject unauthenticated callers when a shared secret is configured.
    # Evolution sends the instance API key in the `apikey` header.
    config = request.app.state.config
    expected = config.whatsapp.webhook_secret or config.whatsapp.evolution_api_key
    if expected:
        provided = request.headers.get("apikey") or payload.apikey
        if not provided or not secrets.compare_digest(provided, expected):
            logger.warning("Rejected WhatsApp webhook with invalid/missing secret")
            return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    bus = request.app.state.bus

    # Only process message events
    if payload.event != "messages.upsert":
        logger.debug("Ignoring webhook event: %s", payload.event)
        return Response(status_code=status.HTTP_200_OK)

    data = payload.data
    key = data.get("key", {})
    message_data = data.get("message", {})
    message_type = data.get("messageType", "")

    # Ignore messages sent by us
    if key.get("fromMe", False):
        logger.debug("Ignoring outgoing message")
        return Response(status_code=status.HTTP_200_OK)

    sender_jid = key.get("remoteJid", "")
    sender_name = data.get("pushName", "")

    # Extract text content based on message type
    text_content = _extract_text(message_data, message_type)

    if text_content:
        logger.info(
            "WhatsApp text from %s (%s): %.80s",
            sender_name,
            sender_jid,
            text_content,
        )

        message = Message(
            role=MessageRole.USER,
            content=text_content,
            channel=ChannelType.WHATSAPP,
            language=Language.AUTO,
            metadata={
                "sender_jid": sender_jid,
                "sender_name": sender_name,
                "message_id": key.get("id", ""),
                "instance": payload.instance,
            },
        )
        await bus.publish_inbound(message)

    elif message_type == "audioMessage":
        # Audio messages — store metadata for future STT processing (Phase 4)
        audio_data = message_data.get("audioMessage", {})
        seconds = audio_data.get("seconds", 0)
        base64_data = data.get("base64", "")

        logger.info(
            "WhatsApp audio from %s (%s): %ds%s",
            sender_name,
            sender_jid,
            seconds,
            " (base64 included)" if base64_data else "",
        )

        # For now, acknowledge audio but explain we can't process it yet
        message = Message(
            role=MessageRole.USER,
            content=f"[Audio message received: {seconds}s]",
            channel=ChannelType.WHATSAPP,
            language=Language.AUTO,
            metadata={
                "sender_jid": sender_jid,
                "sender_name": sender_name,
                "message_id": key.get("id", ""),
                "instance": payload.instance,
                "audio_seconds": seconds,
                "audio_base64": base64_data,
                "message_type": "audio",
            },
        )
        await bus.publish_inbound(message)

    else:
        logger.debug(
            "Ignoring unsupported message type '%s' from %s",
            message_type,
            sender_jid,
        )

    return Response(status_code=status.HTTP_200_OK)


def _extract_text(message_data: dict[str, Any], message_type: str) -> str:
    """Extract text content from various WhatsApp message types.

    Supports:
    - conversation: plain text messages
    - extendedTextMessage: text with URL preview or formatting
    """
    if message_type == "conversation":
        return message_data.get("conversation", "")

    if message_type == "extendedTextMessage":
        ext = message_data.get("extendedTextMessage", {})
        return ext.get("text", "")

    return ""
