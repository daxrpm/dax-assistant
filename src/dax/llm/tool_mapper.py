"""Maps MCP tool schemas to OpenAI function-calling format.

We use the OpenAI tool schema as the internal interchange format; each
provider adapter translates it into its own SDK's shape.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def mcp_tools_to_openai(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a list of MCP tool schemas to OpenAI function-calling format.

    MCP format:
        {"name": "...", "description": "...", "inputSchema": {...}}

    OpenAI format:
        {"type": "function", "function": {"name": "...",
        "description": "...", "parameters": {...}}}
    """
    openai_tools: list[dict[str, Any]] = []

    for tool in mcp_tools:
        name = tool.get("name", "")
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})

        openai_tool = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": (
                    input_schema
                    if input_schema
                    else {"type": "object", "properties": {}}
                ),
            },
        }
        openai_tools.append(openai_tool)

    return openai_tools


def parse_tool_calls_from_response(
    response_tool_calls: list[Any],
    server_lookup: dict[str, str],
) -> list[dict[str, Any]]:
    """Parse tool calls from a litellm response into our internal format.

    Args:
        response_tool_calls: Tool calls from the LLM response.
        server_lookup: Mapping of tool_name → server_name.

    Returns:
        List of dicts with id, server_name, tool_name, arguments.
    """
    import json

    parsed: list[dict[str, Any]] = []

    for tc in response_tool_calls:
        func = tc.function if hasattr(tc, "function") else tc.get("function", {})
        tool_name = func.name if hasattr(func, "name") else func.get("name", "")
        arguments_raw = (
            func.arguments
            if hasattr(func, "arguments")
            else func.get("arguments", "{}")
        )

        if isinstance(arguments_raw, str):
            try:
                arguments = json.loads(arguments_raw)
            except json.JSONDecodeError:
                logger.warning("Failed to parse tool arguments: %s", arguments_raw)
                arguments = {}
        else:
            arguments = arguments_raw

        call_id = tc.id if hasattr(tc, "id") else tc.get("id", "")
        server_name = server_lookup.get(tool_name, "unknown")

        parsed.append({
            "id": call_id,
            "server_name": server_name,
            "tool_name": tool_name,
            "arguments": arguments,
        })

    return parsed


# Spanish → English keyword expansion for tool matching.
# Covers common assistant queries so the filter works bilingually.
_ES_EN_KEYWORDS: dict[str, list[str]] = {
    "archivo": ["file", "read", "write"],
    "archivos": ["file", "files", "list", "directory"],
    "carpeta": ["directory", "folder", "list"],
    "directorio": ["directory", "list", "tree"],
    "escritorio": ["desktop", "directory", "list", "file"],
    "ver": ["list", "read", "view", "get", "search"],
    "buscar": ["search", "find", "query"],
    "crear": ["create", "write", "new", "add"],
    "borrar": ["delete", "remove"],
    "editar": ["edit", "update", "write"],
    "leer": ["read", "get", "fetch"],
    "lista": ["list", "get"],
    "música": ["music", "play", "spotify", "track"],
    "canción": ["song", "track", "play", "music"],
    "reproducir": ["play", "music", "spotify"],
    "luz": ["light", "turn", "switch", "home"],
    "luces": ["lights", "turn", "switch", "home"],
    "temperatura": ["temperature", "climate", "thermostat"],
    "calendario": ["calendar", "event", "schedule"],
    "evento": ["event", "calendar", "create"],
    "nota": ["note", "notes", "write"],
    "tarea": ["task", "todo", "create"],
    "proyecto": ["project", "list"],
    "base": ["database", "sql", "query"],
    "datos": ["data", "database", "query"],
    "comando": ["command", "shell", "execute"],
    "ejecutar": ["execute", "run", "command", "shell"],
    "terminal": ["shell", "command", "execute"],
    "tiempo": ["time", "weather"],
    "hora": ["time", "current"],
    "web": ["fetch", "url", "web"],
    "página": ["page", "fetch", "web", "url"],
}


def filter_tools_by_relevance(
    tools: list[dict[str, Any]],
    query: str,
    max_tools: int = 8,
) -> list[dict[str, Any]]:
    """Filter tools based on keyword relevance to the user's query.

    Supports bilingual (ES/EN) queries via keyword expansion.
    Returns the most relevant tools up to max_tools.
    """
    if len(tools) <= max_tools:
        return tools

    query_lower = query.lower()
    query_words = set(re.findall(r"\w+", query_lower))

    # Expand Spanish keywords to English equivalents
    expanded_words = set(query_words)
    for word in query_words:
        if word in _ES_EN_KEYWORDS:
            expanded_words.update(_ES_EN_KEYWORDS[word])

    scored: list[tuple[float, dict[str, Any]]] = []

    for tool in tools:
        name = tool.get("name", "").lower()
        description = tool.get("description", "").lower()
        tool_text = f"{name} {description}"
        tool_words = set(re.findall(r"\w+", tool_text))

        # Score: expanded keyword matches + name match bonus
        word_matches = len(expanded_words & tool_words)
        name_bonus = 3.0 if any(w in name for w in expanded_words) else 0.0
        score = word_matches + name_bonus

        scored.append((score, tool))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [tool for _, tool in scored[:max_tools]]
