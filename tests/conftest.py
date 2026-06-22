"""Shared test fixtures for Dax Assistant."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from dax.core.config import DaxConfig, load_config
from dax.core.models import ChannelType, Conversation, Language, Message, MessageRole
from dax.orchestrator.bus import MessageBus
from dax.storage.database import Database

if TYPE_CHECKING:
    from pathlib import Path

# Env vars that, if present in the developer's shell or .env, would leak into
# DaxConfig and make tests depend on the local machine.
_LEAKY_ENV = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
}


@pytest.fixture(autouse=True)
def isolate_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent of the developer's real .env and DAX_* env vars.

    DaxConfig reads ``.env`` and the process environment with higher priority
    than init kwargs, so without this a real local ``.env`` (e.g. a configured
    password hash) would override values that tests pass explicitly.
    """
    monkeypatch.setitem(DaxConfig.model_config, "env_file", None)
    for var in list(os.environ):
        if var.startswith("DAX_") or var in _LEAKY_ENV:
            monkeypatch.delenv(var, raising=False)


@pytest.fixture
def sample_message() -> Message:
    """A simple user message for testing."""
    return Message(
        role=MessageRole.USER,
        content="What time is it?",
        channel=ChannelType.WEB,
        language=Language.ENGLISH,
    )


@pytest.fixture
def sample_conversation(sample_message: Message) -> Conversation:
    """A conversation with one message."""
    conv = Conversation(channel=ChannelType.WEB)
    conv.add_message(sample_message)
    return conv


@pytest.fixture
def default_config() -> DaxConfig:
    """Default configuration with no file overrides."""
    return DaxConfig()


@pytest.fixture
def config_from_file(tmp_path: Path) -> DaxConfig:
    """Configuration loaded from a temporary TOML file."""
    toml_content = """
[general]
name = "TestDax"
log_level = "DEBUG"

[storage]
database_path = "{db_path}"
""".format(db_path=str(tmp_path / "test.db"))

    config_file = tmp_path / "dax.toml"
    config_file.write_text(toml_content)
    return load_config(config_file)


@pytest.fixture
def message_bus() -> MessageBus:
    """An initialized message bus."""
    bus = MessageBus()
    bus.start()
    return bus


@pytest.fixture
async def database(tmp_path: Path) -> Database:
    """An initialized in-memory-like SQLite database."""
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    await db.start()
    yield db  # type: ignore[misc]
    await db.stop()
