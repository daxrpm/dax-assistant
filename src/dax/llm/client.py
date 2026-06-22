"""Shared LLM helpers: the system prompt and the message builder.

The conversation is assembled in OpenAI chat format (the de-facto interchange
shape). Each provider adapter under ``dax.llm.providers`` translates this into
its own SDK's native format, so the orchestrator stays provider-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dax.core.models import Message

SYSTEM_PROMPT = """You are Dax, a helpful personal AI assistant. You are running locally \
on the user's machine and have access to tools for interacting with their services \
(calendar, files, smart home, music, shell commands).

Respond concisely and helpfully. When a user asks you to do something, use the \
available tools to accomplish it. If you're unsure about something, ask for clarification.

You understand both Spanish and English. Respond in the same language the user uses."""


def build_messages_for_llm(
    user_message: Message,
    conversation_history: list[Message] | None = None,
    system_prompt: str = SYSTEM_PROMPT,
) -> list[dict[str, Any]]:
    """Build the OpenAI-format message list for an LLM call.

    Converts our Message objects into OpenAI-compatible dicts: a system
    message, then prior history, then the current user message.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]

    if conversation_history:
        for msg in conversation_history:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

    messages.append({
        "role": "user",
        "content": user_message.content,
    })

    return messages
