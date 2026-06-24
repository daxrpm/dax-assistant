"""Telegram channel — long-polling bot via the Telegram Bot API.

Uses long-polling (getUpdates), so no public URL or open port is needed —
ideal for a local personal assistant. Create a bot with @BotFather and put its
token in config. Implemented over httpx directly (no extra dependency).

The channel is bidirectional:
- Inbound: a background poll loop reads updates and publishes them to the bus.
- Outbound: send() delivers assistant replies back to the originating chat.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx

from dax.core.exceptions import ChannelError
from dax.core.models import ChannelType, Language, Message, MessageRole

if TYPE_CHECKING:
    from dax.core.config import TelegramConfig
    from dax.orchestrator.bus import MessageBus

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"


class TelegramChannel:
    """Telegram bot channel using long-polling."""

    def __init__(self, config: TelegramConfig, bus: MessageBus) -> None:
        self._config = config
        self._bus = bus
        self._token = config.bot_token
        self._allowed = set(config.allowed_user_ids)
        self._client: httpx.AsyncClient | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._offset = 0

    @property
    def name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        if not self._token:
            logger.warning("Telegram enabled but no bot_token set — channel disabled")
            return
        self._client = httpx.AsyncClient(
            base_url=f"{_API_BASE}/bot{self._token}",
            timeout=httpx.Timeout(40.0),
        )
        # Verify the token and learn the bot identity before polling.
        try:
            resp = await self._client.get("/getMe")
            resp.raise_for_status()
            me = resp.json().get("result", {})
            logger.info("Telegram bot connected: @%s", me.get("username", "?"))
        except Exception as e:
            logger.error("Telegram getMe failed — check bot_token: %s", e)
            await self._client.aclose()
            self._client = None
            return

        self._poll_task = asyncio.create_task(self._poll_loop(), name="telegram-poll")
        logger.info("Telegram channel started (long-polling)")

    async def stop(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Telegram channel stopped")

    async def _poll_loop(self) -> None:
        """Long-poll getUpdates and publish inbound text messages to the bus."""
        assert self._client is not None
        while True:
            try:
                resp = await self._client.get(
                    "/getUpdates",
                    params={"offset": self._offset, "timeout": 30},
                )
                resp.raise_for_status()
                updates = resp.json().get("result", [])
                for update in updates:
                    self._offset = update["update_id"] + 1
                    await self._handle_update(update)
            except asyncio.CancelledError:
                raise
            except httpx.HTTPError as e:
                logger.warning("Telegram poll error: %s — retrying in 5s", e)
                await asyncio.sleep(5)
            except Exception:
                logger.exception("Unexpected Telegram poll failure")
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        text = msg.get("text", "")
        if not text:
            return

        from_user = msg.get("from", {})
        user_id = from_user.get("id")
        chat_id = msg.get("chat", {}).get("id")

        # Access control: when allowed_user_ids is set, reject everyone else.
        if self._allowed and user_id not in self._allowed:
            logger.warning("Telegram message from unauthorized user %s ignored", user_id)
            await self._send_text(chat_id, "Sorry, you're not authorized to use this bot.")
            return

        name = from_user.get("first_name", "") or from_user.get("username", "")
        logger.info("Telegram message from %s (%s): %.80s", name, user_id, text)

        message = Message(
            role=MessageRole.USER,
            content=text,
            channel=ChannelType.TELEGRAM,
            language=Language.AUTO,
            metadata={
                "chat_id": str(chat_id),
                "sender_id": str(user_id),
                "sender_name": name,
                "session_id": f"telegram:{chat_id}",
            },
        )
        await self._bus.publish_inbound(message)

    async def send(self, message: Message) -> None:
        """Deliver an assistant reply back to the originating Telegram chat."""
        chat_id = message.metadata.get("chat_id", "")
        if not chat_id:
            logger.warning("Cannot send Telegram message: no chat_id in metadata")
            return
        await self._send_text(chat_id, message.content)

    async def _send_text(self, chat_id: Any, text: str) -> None:
        if not self._client or not chat_id:
            return
        # Telegram caps messages at 4096 chars — split long replies.
        for chunk in _split_message(text, 4096):
            try:
                resp = await self._client.post(
                    "/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ChannelError(
                    f"Telegram sendMessage failed {e.response.status_code}: "
                    f"{e.response.text}"
                ) from e
            except httpx.RequestError as e:
                raise ChannelError(f"Telegram request failed: {e}") from e


def _split_message(text: str, limit: int) -> list[str]:
    """Split text into chunks no longer than *limit* characters."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks
