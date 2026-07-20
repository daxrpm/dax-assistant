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
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ValidationError

from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.storage.secrets import SecretStore
from dax.web.dependencies import BusDep, ConfigDep, SecretStoreDep

router = APIRouter(tags=["webhooks"])

logger = logging.getLogger(__name__)

_MAX_WEBHOOK_BYTES = 1_048_576
_WEBHOOK_SECRET_KEYS = (
    "DAX_WHATSAPP__WEBHOOK_SECRET",
    "DAX_WHATSAPP__EVOLUTION_API_KEY",
)


class WebhookEnvelope(BaseModel):
    """Evolution API v2 webhook outer envelope."""

    event: str
    instance: str
    data: dict[str, Any]
    date_time: str = ""
    sender: str = ""
    server_url: str = ""
    apikey: str = ""


async def _bounded_payload(request: Request) -> WebhookEnvelope:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > _MAX_WEBHOOK_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE)
    try:
        return WebhookEnvelope.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY) from exc


WebhookPayloadDep = Annotated[WebhookEnvelope, Depends(_bounded_payload)]


def _webhook_secret(config: ConfigDep, store: SecretStore) -> str | None:
    """Resolve persisted secrets, failing rather than silently disabling auth."""
    stored = [store.get(key) for key in _WEBHOOK_SECRET_KEYS]
    configured = [
        config.whatsapp.webhook_secret,
        config.whatsapp.evolution_api_key,
    ]
    for configured_value, stored_value in zip(configured, stored, strict=True):
        if configured_value:
            if configured_value.startswith("{env:"):
                if not stored_value:
                    raise RuntimeError("configured webhook secret is unavailable")
                return stored_value
            return configured_value
        if stored_value:
            return stored_value
    return None


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    payload: WebhookPayloadDep,
    config: ConfigDep,
    bus: BusDep,
    store: SecretStoreDep,
) -> Response:
    """Receive and process WhatsApp messages from Evolution API v2.

    Handles:
    - Text messages (conversation, extendedTextMessage)
    - Audio messages (audioMessage) — queued for future STT processing

    All other event types are logged and acknowledged.
    """
    if not config.whatsapp.enabled:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    # An enabled public webhook must always have a shared secret.
    # Evolution sends the instance API key in the `apikey` header.
    try:
        expected = _webhook_secret(config, store)
    except Exception:
        logger.exception("WhatsApp webhook secret is unavailable")
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    if not expected:
        logger.error("WhatsApp is enabled without a webhook secret")
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    provided = request.headers.get("apikey") or payload.apikey
    if not provided or not secrets.compare_digest(provided, expected):
        logger.warning("Rejected WhatsApp webhook with invalid/missing secret")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

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
        conversation = message_data.get("conversation", "")
        return conversation if isinstance(conversation, str) else ""

    if message_type == "extendedTextMessage":
        ext = message_data.get("extendedTextMessage", {})
        if isinstance(ext, dict):
            text = ext.get("text", "")
            return text if isinstance(text, str) else ""

    return ""
