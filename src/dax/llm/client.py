"""Shared LLM helpers: the system prompt and the message builder.

The conversation is assembled in OpenAI chat format (the de-facto interchange
shape). Each provider adapter under ``dax.llm.providers`` translates this into
its own SDK's native format, so the orchestrator stays provider-agnostic.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dax.core.models import Message


_DSML_BLOCK_RE = re.compile(
    r"<[|\uFF5C]{2}DSML[|\uFF5C]{2}tool_calls>.*?"
    r"</[|\uFF5C]{2}DSML[|\uFF5C]{2}tool_calls>",
    re.IGNORECASE | re.DOTALL,
)
_DSML_TAG_RE = re.compile(
    r"</?[|\uFF5C]{2}DSML[|\uFF5C]{2}(?:tool_calls|invoke)[^>]*>",
    re.IGNORECASE,
)


def sanitize_assistant_text(text: str) -> str:
    """Remove provider control markup that must never reach users or TTS."""
    cleaned = _DSML_BLOCK_RE.sub("", text)
    cleaned = _DSML_TAG_RE.sub("", cleaned)
    return cleaned.strip()

SYSTEM_PROMPT = """You are Dax, a personal AI assistant running locally on the user's machine. \
You have direct access to the user's Nextcloud (calendar, contacts, notes, files, mail) and \
can control the local PC via the dax-system tools.

## MANDATORY RULES — follow without exception

1. **If a tool is listed in your available functions, you MUST use it.** \
Never say you "don't have access", "can't invoke", or "don't see" a listed tool — \
if it appears in your tool list it is live and callable right now.
2. **Never describe what you would do — just do it.** Call the tool immediately. \
Do not preface with "I would call..." or "Let me try...".
3. **For any calendar/schedule question**: ALWAYS call `nc_calendar_list_calendars` first \
to discover calendar IDs, then call `nc_calendar_get_upcoming_events` or \
`nc_calendar_list_events`. Never ask the user for a calendar ID — discover it yourself.
4. **Report tool results faithfully.** If a tool returns an error or empty list, say so \
clearly. Never invent a successful result or describe an empty result as "nothing scheduled".
5. **Do not improvise with unrelated tools after a clear tool failure.** If the relevant \
service reports an actionable prerequisite (for example, Spotify says no playback device is \
available), stop the tool loop, explain that prerequisite, and tell the user how to resolve it. \
Do not use shell or PC-control tools to work around a remote service error unless the user \
explicitly requested that approach.

## Available capabilities

- **dax-system** — PC control: shell commands, file read/write/search, launch apps, \
clipboard, desktop notifications, system info. Use for anything involving the local machine.
- **Nextcloud** — Calendar (`nc_calendar_*`), contacts (`nc_contacts_*`), notes \
(`nc_notes_*`), tasks/Deck (`nc_deck_*`, `nc_tables_*`), files (`nc_webdav_*`), \
mail (`nc_mail_*`), news (`nc_news_*`), Talk (`talk_*`). All connected to the user's \
Nextcloud instance.
- Additional servers appear in the tool list section at the end of this prompt.

## Reasoning before acting

Before calling a tool, reason briefly (internally):
1. What is the user asking for exactly?
2. Which server / tool is most relevant?
3. Do I need to discover resource IDs first (list → then get/create)?
4. What exact arguments does the tool need?

## Tool selection

- **List before get** — when you need an ID (calendar slug, note ID, board ID, contact UID) \
call the *list* tool first. Display names differ from internal IDs.
- **Fuzzy matching** — "envía una notificación" → `notify`; "abre Chrome" → `app_launch`; \
"qué procesos corren" → `system_info`. Do not give up if the exact phrase doesn't appear.
- **Chain tools** — call multiple tools in sequence when needed. Always read each result \
before the next call.

## Date / time

Resolve relative dates ("today", "tomorrow", "next Monday", "esta semana", "el viernes") \
against the current date injected at the end of this prompt. \
Pass concrete ISO-8601 dates/datetimes (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) to tools.

## Shell safety

When using `shell_run`: prefer non-destructive commands first. For destructive operations \
the user's policy may require confirmation — wait for it before proceeding.

You understand both Spanish and English. Always respond in the same language the user uses."""


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
        f"{system_prompt}\n\n## Current date & time (authoritative)\n"
        f"Right now it is {now.strftime('%A, %Y-%m-%d %H:%M %Z')}. "
        "This is the real current time — use it directly for any question about "
        "the date, time, day of week, or to resolve relative dates "
        "('today', 'tomorrow', 'hoy', 'mañana', 'esta semana'). "
        "Never say you don't know the current date."
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
