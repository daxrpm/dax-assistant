"""WhatsApp channel — sends responses via Evolution API v2.

Incoming messages are received via the webhook route (web/routes/webhooks.py).
This channel handles OUTBOUND message delivery to WhatsApp contacts.

Evolution API v2 endpoints:
- Send text: POST /message/sendText/{instance}
- Send audio: POST /message/sendWhatsAppAudio/{instance}
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from dax.core.exceptions import ChannelError

if TYPE_CHECKING:
    from dax.core.config import WhatsAppConfig
    from dax.core.models import Message

logger = logging.getLogger(__name__)


class WhatsAppChannel:
    """WhatsApp outbound channel via Evolution API v2.

    Sends text (and optionally audio) responses to WhatsApp contacts.
    Incoming messages arrive via webhook — see webhooks.py.
    """

    def __init__(self, config: WhatsAppConfig) -> None:
        self._config = config
        self._base_url = config.evolution_api_url.rstrip("/")
        self._instance = config.evolution_api_instance
        self._api_key = config.evolution_api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "whatsapp"

    async def start(self) -> None:
        """Initialize the HTTP client for Evolution API calls."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"apikey": self._api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(30.0),
        )
        logger.info(
            "WhatsApp channel started (instance: %s, url: %s)",
            self._instance,
            self._base_url,
        )

    async def stop(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("WhatsApp channel stopped")

    async def send(self, message: Message) -> None:
        """Send a response message to a WhatsApp contact.

        The recipient JID is extracted from the message metadata
        (set by the webhook handler when the original message arrived).
        """
        if not self._client:
            raise ChannelError("WhatsApp channel not started")

        sender_jid = message.metadata.get("sender_jid", "")
        if not sender_jid:
            logger.warning("Cannot send WhatsApp message: no sender_jid in metadata")
            return

        # Extract phone number from JID (e.g., "5531982968011@s.whatsapp.net" → "5531982968011")
        number = sender_jid.split("@")[0]

        await self._send_text(number, message.content)

    async def _send_text(self, number: str, text: str) -> dict[str, Any]:
        """Send a text message via Evolution API v2.

        POST /message/sendText/{instance}
        """
        if not self._client:
            raise ChannelError("WhatsApp channel not started")

        payload = {
            "number": number,
            "text": text,
        }

        try:
            response = await self._client.post(
                f"/message/sendText/{self._instance}",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            logger.info("WhatsApp text sent to %s", number)
            return result
        except httpx.HTTPStatusError as e:
            raise ChannelError(
                f"Evolution API error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise ChannelError(f"Evolution API request failed: {e}") from e

    async def send_audio(self, number: str, audio_url: str) -> dict[str, Any]:
        """Send a voice note via Evolution API v2.

        POST /message/sendWhatsAppAudio/{instance}
        """
        if not self._client:
            raise ChannelError("WhatsApp channel not started")

        payload = {
            "number": number,
            "audio": audio_url,
        }

        try:
            response = await self._client.post(
                f"/message/sendWhatsAppAudio/{self._instance}",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            logger.info("WhatsApp audio sent to %s", number)
            return result
        except httpx.HTTPStatusError as e:
            raise ChannelError(
                f"Evolution API audio error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise ChannelError(f"Evolution API audio request failed: {e}") from e
