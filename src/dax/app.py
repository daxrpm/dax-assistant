"""Application bootstrap and lifecycle management.

Wires all components together via dependency injection and manages
the startup/shutdown sequence. Runs uvicorn embedded in the asyncio loop.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import uvicorn

from dax.channels.telegram_channel import TelegramChannel
from dax.channels.voice_channel import VoiceChannel
from dax.channels.web_channel import WebChannel
from dax.channels.whatsapp_channel import WhatsAppChannel
from dax.core.config import DaxConfig, load_config
from dax.core.logbuffer import LogBuffer
from dax.core.policy import ToolPolicy
from dax.core.shell_allow import ShellAllowlist
from dax.llm.factory import build_router
from dax.mcp.manager import MCPManager
from dax.orchestrator.agent import Agent
from dax.orchestrator.approval import ApprovalManager
from dax.orchestrator.bus import MessageBus
from dax.orchestrator.dispatcher import Dispatcher
from dax.storage.database import Database
from dax.storage.repository import ConversationRepository
from dax.storage.secrets import SecretStore
from dax.web.server import create_app

if TYPE_CHECKING:
    from dax.voice.pipeline import VoicePipeline

logger = structlog.get_logger(__name__)


def _configure_logging(log_level: str) -> None:
    """Set up structlog with console rendering."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class DaxApp:
    """Main application — orchestrates all components.

    Usage:
        app = DaxApp.from_config_path(config_path)
        await app.run()
    """

    def __init__(
        self, config: DaxConfig, config_path: Path | None = None
    ) -> None:
        self._config = config
        self._config_path = config_path or Path("config/dax.toml")
        self._shutdown_event = asyncio.Event()

        # Capture stdlib logs into a ring buffer for the web Logs viewer.
        self._log_buffer = LogBuffer()
        logging.getLogger().addHandler(self._log_buffer)

        # Core components
        self._bus = MessageBus()
        self._database = Database(config.storage.database_path)
        self._repository = ConversationRepository(self._database)

        # Encrypted secret store (replaces .env as the source of truth).
        self._secrets = SecretStore(config.storage.database_path)

        # LLM router — decoupled, multi-provider (official SDKs). The default
        # provider plus the configured fallback chain, all behind the
        # LLMProvider port.
        self._llm = build_router(config.llm)

        # MCP server manager
        self._mcp = MCPManager(config.mcp)

        # Tool execution policy + human-in-the-loop confirmation gate.
        self._policy = ToolPolicy.from_config(config.tools.policy)
        self._approval = ApprovalManager(
            timeout_seconds=config.tools.confirm_timeout_seconds
        )

        # Authoritative shell-command allowlist. Mutations (UI edits or the agent
        # saving an approved command) update config + rewrite the TOML in place.
        self._shell_allow = ShellAllowlist(config.tools.shell_allow)
        self._shell_allow.set_on_change(self._persist_shell_allow)

        # Channels
        self._channels: dict[
            str, VoiceChannel | WebChannel | WhatsAppChannel | TelegramChannel
        ] = {}

        # Voice pipeline (initialized in start() if enabled)
        self._voice_pipeline: VoicePipeline | None = None

        # Web
        self._web_app = create_app(config=config, bus=self._bus)
        self._uvicorn_server: uvicorn.Server | None = None

        self._agent: Agent | None = None
        self._dispatcher: Dispatcher | None = None

    @classmethod
    def from_config_path(cls, config_path: Path | None = None) -> DaxApp:
        """Create a DaxApp instance from a config file path."""
        config = load_config(config_path)
        _configure_logging(config.log_level)
        return cls(config, config_path=config_path)

    @property
    def config(self) -> DaxConfig:
        return self._config

    def _persist_shell_allow(self, commands: list[str]) -> None:
        """Mirror the live shell allowlist into config and rewrite the TOML."""
        from dax.core.config_io import write_config_toml

        object.__setattr__(self._config.tools, "shell_allow", list(commands))
        try:
            write_config_toml(self._config, self._secrets, self._config_path)
        except Exception:
            logger.exception("Failed to persist shell allowlist")

    @property
    def web_app(self) -> object:
        """Expose FastAPI app for testing."""
        return self._web_app

    async def start(self) -> None:
        """Initialize all components in dependency order."""
        log = logger.bind(app="dax")
        log.info("Starting Dax Assistant", version="0.1.0", name=self._config.name)

        # 1. Storage
        await self._database.start()
        log.info("Storage ready")

        # Deliver live log records to web subscribers on this loop.
        self._log_buffer.bind_loop(asyncio.get_running_loop())
        if hasattr(self._web_app, "state"):
            self._web_app.state.log_buffer = self._log_buffer  # type: ignore[union-attr]
            self._web_app.state.tool_policy = self._policy  # type: ignore[union-attr]
            # The live shell allowlist the agent consults, so the Commands page
            # can read/edit it, and config_path for standalone TOML persistence.
            self._web_app.state.shell_allow = self._shell_allow
            self._web_app.state.config_path = self._config_path
            # Expose the secret store + the app itself so settings endpoints can
            # persist secrets to SQLite and reload live channels (Telegram).
            self._web_app.state.secret_store = self._secrets
            self._web_app.state.dax_app = self

        # 2. Message bus
        self._bus.start()
        log.info("Message bus ready")

        # 3. MCP servers
        await self._mcp.start()
        # Expose manager + repository on web app state for API endpoints.
        if hasattr(self._web_app, "state"):
            self._web_app.state.mcp_manager = self._mcp  # type: ignore[union-attr]
            self._web_app.state.repository = self._repository  # type: ignore[union-attr]
            # Expose the router so the settings API can rebuild it in place
            # when the LLM config changes (no restart needed).
            self._web_app.state.llm_router = self._llm  # type: ignore[union-attr]
        log.info(
            "MCP ready",
            servers=len(self._mcp._clients),
            tools=self._mcp.registry.tool_count,
        )

        # 4. LLM availability check
        llm_available = await self._llm.is_available()
        if llm_available:
            log.info("LLM ready", provider=self._llm.name)
        else:
            log.warning("LLM not available — responses will fail")

        # 5. Channels
        web_channel = WebChannel()
        await web_channel.start()
        self._channels["web"] = web_channel

        if self._config.whatsapp.enabled:
            wa_channel = WhatsAppChannel(self._config.whatsapp)
            await wa_channel.start()
            self._channels["whatsapp"] = wa_channel

        if self._config.telegram.enabled:
            tg_channel = TelegramChannel(self._config.telegram, self._bus)
            await tg_channel.start()
            self._channels["telegram"] = tg_channel

        # Voice channel (always registered so dispatcher can route to it)
        if self._config.voice.enabled:
            voice_channel = VoiceChannel()
            await voice_channel.start()
            self._channels["voice"] = voice_channel

        log.info("Channels ready", channels=list(self._channels.keys()))

        # 6. Agent
        self._agent = Agent(
            bus=self._bus,
            llm=self._llm,  # type: ignore[arg-type]
            tools=self._mcp,  # type: ignore[arg-type]
            storage=self._repository,  # type: ignore[arg-type]
            policy=self._policy,
            approval=self._approval,
            shell_allow=self._shell_allow,
            max_tools=self._config.llm.max_tools,
            memory_path=self._config.memory_path,
        )
        await self._agent.start()

        # Wire the confirmation gate to the web UI: deliver requests over the
        # chat WebSocket, and let the WS route resolve them.
        from dax.web.routes.chat import ws_manager

        self._approval.set_notifier(ws_manager.broadcast)
        # Stream agent events (tool calls, thinking) to the web UI in real time.
        async def _broadcast_event(event: dict) -> None:
            await ws_manager.broadcast({"type": "agent_event", "event": event})

        self._agent.set_event_broadcaster(_broadcast_event)  # type: ignore[union-attr]
        if hasattr(self._web_app, "state"):
            self._web_app.state.approval = self._approval  # type: ignore[union-attr]
        log.info("Agent ready")

        # 7. Dispatcher (routes outbound messages to ALL channels)
        self._dispatcher = Dispatcher(
            bus=self._bus,
            channels=self._channels,  # type: ignore[arg-type]
        )
        await self._dispatcher.start()
        log.info("Dispatcher ready")

        # 8. Voice pipeline (runs in dedicated thread, needs the event loop)
        if self._config.voice.enabled and "voice" in self._channels:
            try:
                from dax.voice.pipeline import VoicePipeline

                loop = asyncio.get_running_loop()
                voice_ch = self._channels["voice"]
                assert isinstance(voice_ch, VoiceChannel)

                self._voice_pipeline = VoicePipeline(
                    config=self._config.voice,
                    bus=self._bus,
                    voice_channel=voice_ch,
                    loop=loop,
                    models_path=self._config.storage.models_path,
                    approval=self._approval,
                )
                self._voice_pipeline.start()
                log.info("Voice pipeline ready")
            except Exception:
                log.exception(
                    "Voice pipeline failed to start — continuing without voice"
                )
                self._voice_pipeline = None

        log.info("Dax Assistant is ready")

    async def reload_telegram(self) -> None:
        """Restart the Telegram channel to apply config changes without a full
        app restart. Stops any running channel, then starts a fresh one when
        enabled. Safe to call when Telegram is disabled (just tears down)."""
        # The dispatcher shares this exact dict reference, so mutating it in
        # place is enough — routing picks up the change immediately.
        existing = self._channels.pop("telegram", None)
        if existing is not None:
            await existing.stop()

        if self._config.telegram.enabled and self._config.telegram.bot_token:
            tg_channel = TelegramChannel(self._config.telegram, self._bus)
            await tg_channel.start()
            self._channels["telegram"] = tg_channel
            logger.info("Telegram channel reloaded")

    async def stop(self) -> None:
        """Shut down all components in reverse order."""
        log = logger.bind(app="dax")
        log.info("Shutting down Dax Assistant")

        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        # Voice pipeline first (it's in a thread)
        if self._voice_pipeline:
            self._voice_pipeline.stop()

        if self._dispatcher:
            await self._dispatcher.stop()
        if self._agent:
            await self._agent.stop()

        for _name, channel in self._channels.items():
            await channel.stop()

        await self._mcp.stop()
        await self._database.stop()

        log.info("Dax Assistant stopped")

    async def run(self) -> None:
        """Run the application with embedded uvicorn server."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._request_shutdown)

        await self.start()

        # Run uvicorn embedded in the same event loop
        uvicorn_config = uvicorn.Config(
            app=self._web_app,
            host=self._config.web.effective_host,
            port=self._config.web.port,
            log_level=self._config.log_level.lower(),
            access_log=False,
        )
        self._uvicorn_server = uvicorn.Server(uvicorn_config)

        try:
            await self._uvicorn_server.serve()
        finally:
            await self._stop_even_if_cancelled()

    async def _stop_even_if_cancelled(self) -> None:
        """Run shutdown to completion even if uvicorn/request cancellation leaks."""
        task = asyncio.create_task(self.stop(), name="dax-shutdown")
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current is not None:
                    current.uncancel()
        await task

    def _request_shutdown(self) -> None:
        """Signal handler — request graceful shutdown."""
        self._shutdown_event.set()
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
