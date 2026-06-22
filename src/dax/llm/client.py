"""Shared LLM helpers: the system prompt and the message builder.

The conversation is assembled in OpenAI chat format (the de-facto interchange
shape). Each provider adapter under ``dax.llm.providers`` translates this into
its own SDK's native format, so the orchestrator stays provider-agnostic.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dax.core.models import Message

SYSTEM_PROMPT = """You are Dax, a helpful personal AI assistant. You are running locally \
on the user's machine and have access to tools for interacting with their services \
(calendar, files, smart home, music, shell commands).

Respond concisely and helpfully. When a user asks you to do something, use the \
available tools to accomplish it. If you're unsure about something, ask for clarification.

Tool usage:
- When the user refers to a named resource (a calendar, address book, notebook, board, \
mailbox, etc.), do NOT guess its identifier. First call the matching "list" tool to \
discover the available items, then use the resource's internal/technical name (the `name` \
or id field) for follow-up calls — it often differs from the human-readable display name \
(e.g. a calendar shown as "EPN" may actually be `epn-1`). Match the user's wording to a \
display name, then pass the corresponding internal name.
- Resolve relative dates ("today", "tomorrow", "this week") against the current date below, \
and pass concrete dates to tools.
- Read a tool's result before answering. If it reports an error, an empty/not-found result, \
or a failure (even inside a "success" payload), say so honestly and, if useful, suggest the \
fix — never present a failed or empty lookup as if there were simply nothing there.

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
    now = datetime.now().astimezone()
    dated_prompt = (
        f"{system_prompt}\n\nCurrent date and time: "
        f"{now.strftime('%A, %Y-%m-%d %H:%M %Z')}."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": dated_prompt},
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
