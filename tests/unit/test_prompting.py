"""Tests for system-prompt assembly (extracted from the Agent in Phase E)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dax.core.models import ChannelType
from dax.llm.client import SYSTEM_PROMPT
from dax.orchestrator.prompting import VOICE_STYLE_PROMPT, SystemPromptBuilder

if TYPE_CHECKING:
    from pathlib import Path


def test_build_without_tools_returns_base_prompt() -> None:
    builder = SystemPromptBuilder(memory_path=None)
    prompt = builder.build([], channel=ChannelType.WEB)
    assert prompt == SYSTEM_PROMPT


def test_build_lists_tool_inventory_grouped_by_server() -> None:
    builder = SystemPromptBuilder(memory_path=None)
    tools = [
        {"name": "play", "server_name": "spotify"},
        {"name": "pause", "server_name": "spotify"},
        {"name": "shell_run", "server_name": "dax-system"},
    ]
    prompt = builder.build(tools, channel=ChannelType.WEB)
    assert "Active tools" in prompt
    assert "**spotify** (2 tools): pause, play" in prompt
    assert "**dax-system** (1 tools): shell_run" in prompt


def test_voice_channel_appends_voice_style() -> None:
    builder = SystemPromptBuilder(memory_path=None)
    web = builder.build([], channel=ChannelType.WEB)
    voice = builder.build([], channel=ChannelType.VOICE)
    assert VOICE_STYLE_PROMPT not in web
    assert voice.endswith(VOICE_STYLE_PROMPT)


def test_memory_block_injects_saved_facts(tmp_path: Path) -> None:
    (tmp_path / "MEMORY.md").write_text("# index — ignored", encoding="utf-8")
    (tmp_path / "likes-tea.md").write_text(
        "---\nname: Drinks\n---\n\nThe user prefers green tea.\n", encoding="utf-8"
    )
    builder = SystemPromptBuilder(memory_path=str(tmp_path))
    prompt = builder.build([], channel=ChannelType.WEB)
    assert "What you remember about the user" in prompt
    assert "**Drinks**: The user prefers green tea." in prompt
    assert "index — ignored" not in prompt  # MEMORY.md is skipped


def test_memory_block_absent_when_no_path() -> None:
    builder = SystemPromptBuilder(memory_path=None)
    assert "remember about the user" not in builder.build([], channel=ChannelType.WEB)
