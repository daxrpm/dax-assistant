"""System-prompt assembly for the agent.

Builds the per-turn system prompt from three parts, kept out of the Agent so the
loop stays focused on orchestration:

1. the base prompt + a live inventory of the tools actually passed this turn
   (prevents "I don't have access" hallucinations),
2. durable user memory (``<memory_path>/*.md`` facts),
3. a voice-reply style addendum for spoken turns.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from dax.core.models import ChannelType
from dax.llm.client import SYSTEM_PROMPT

if TYPE_CHECKING:
    from collections.abc import Sequence

# Appended to the system prompt for voice turns: the reply is read aloud by TTS,
# so it must be plain spoken language — no markdown the synthesizer would dictate.
VOICE_STYLE_PROMPT = """

## Voice reply style (this turn is spoken aloud)
Your answer will be read by a text-to-speech voice. Reply in plain, natural \
spoken Spanish/English:
- NO markdown whatsoever — no asterisks, **bold**, _italics_, `code`, #headings, \
bullet lists, tables or emoji. They get dictated literally and sound terrible.
- Be brief and conversational, like a smart speaker. One or two short sentences \
when possible; for lists, say them as a natural sentence ("tienes tres eventos: …").
- Spell things out the way you'd say them, not write them."""


def _tool_inventory(available_tools: Sequence[dict[str, Any]]) -> str:
    """Append a concrete live tool inventory to the base system prompt.

    Grouping by server_name and listing tool names makes it unambiguous to the
    model which tools exist right now — preventing hallucinated "I don't have
    access" responses when tools are actually registered.
    """
    if not available_tools:
        return SYSTEM_PROMPT

    by_server: dict[str, list[str]] = {}
    for tool in available_tools:
        server = tool.get("server_name", "unknown")
        by_server.setdefault(server, []).append(tool["name"])

    lines = ["\n\n## Active tools — available right now in this session"]
    for server, names in sorted(by_server.items()):
        tool_list = ", ".join(sorted(names))
        lines.append(f"- **{server}** ({len(names)} tools): {tool_list}")
    lines.append(
        "\nUse these tools directly. Do NOT say you lack access — "
        "if a tool is listed above you can call it."
    )
    return SYSTEM_PROMPT + "\n".join(lines)


class SystemPromptBuilder:
    """Assembles the per-turn system prompt (tools + memory + voice style)."""

    def __init__(self, memory_path: str | None = None) -> None:
        # Long-term memory: user-curated facts in <memory_path>/*.md, injected
        # so the assistant actually "remembers" them across conversations.
        self._memory_path = memory_path

    def build(
        self,
        available_tools: Sequence[dict[str, Any]],
        *,
        channel: ChannelType,
    ) -> str:
        """Return the full system prompt for this turn."""
        prompt = _tool_inventory(available_tools)
        prompt += self._memory_block()
        if channel is ChannelType.VOICE:
            prompt += VOICE_STYLE_PROMPT
        return prompt

    def _memory_block(self) -> str:
        """Read user-curated memory files and format them for the system prompt.

        Each ``<memory_path>/*.md`` file (except the MEMORY.md index) is a single
        fact with optional frontmatter (name/description/type). We surface the
        title and body so the model can use them — this is what makes the
        memories saved in the UI actually take effect in conversations.
        """
        if not self._memory_path:
            return ""

        mem_dir = Path(self._memory_path).expanduser()
        if not mem_dir.is_dir():
            return ""

        facts: list[str] = []
        for path in sorted(mem_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            name = path.stem.replace("-", " ")
            body = text
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2].strip()
                    for line in parts[1].splitlines():
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip() or name
            body = body.strip()
            if body:
                facts.append(f"- **{name}**: {body}")

        if not facts:
            return ""
        return (
            "\n\n## What you remember about the user\n"
            "These are durable facts the user saved. Treat them as true and "
            "apply them without asking again:\n" + "\n".join(facts)
        )
