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
# Servers whose tools are always included regardless of query relevance
# (small footprint, high utility — dax-system has ≤ 15 tools).
_ALWAYS_INCLUDE_SERVERS: frozenset[str] = frozenset({"dax-system"})

_ES_EN_KEYWORDS: dict[str, list[str]] = {
    "archivo": ["file", "read", "write", "fs"],
    "archivos": ["file", "files", "list", "directory", "fs"],
    "carpeta": ["directory", "folder", "list", "fs"],
    "directorio": ["directory", "list", "tree", "fs"],
    "escritorio": ["desktop", "directory", "list", "file"],
    "ver": ["list", "read", "view", "get", "search"],
    "buscar": ["search", "find", "query"],
    "crear": ["create", "write", "new", "add"],
    "borrar": ["delete", "remove"],
    "editar": ["edit", "update", "write"],
    "leer": ["read", "get", "fetch"],
    "lista": ["list", "get"],
    "música": ["music", "play", "spotify", "track", "media"],
    "musica": ["music", "play", "spotify", "track", "media"],
    "canción": ["song", "track", "play", "music"],
    "cancion": ["song", "track", "play", "music"],
    "spoty": ["spotify", "music", "play", "track"],
    "pon": ["play", "spotify", "music", "track"],
    "ponla": ["play", "spotify", "music", "track"],
    "ponme": ["play", "spotify", "music", "track"],
    "suena": ["play", "spotify", "music", "track"],
    "rola": ["song", "track", "play", "spotify", "music"],
    "tema": ["song", "track", "play", "spotify", "music"],
    "reproducir": ["play", "music", "spotify", "media"],
    "reproduce": ["play", "music", "spotify", "media"],
    "pausa": ["pause", "spotify", "playback", "music"],
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
    "comando": ["command", "shell", "execute", "run"],
    "ejecutar": ["execute", "run", "command", "shell"],
    "terminal": ["shell", "command", "execute", "run"],
    "pc": ["shell", "execute", "system", "command", "run"],
    "computadora": ["shell", "execute", "system", "command"],
    "sistema": ["system", "shell", "info", "execute"],
    "app": ["launch", "app", "open", "application"],
    "abrir": ["open", "launch", "app"],
    "aplicación": ["application", "app", "launch", "open"],
    "portapapeles": ["clipboard", "copy", "paste"],
    "notificación": ["notify", "notification"],
    "notificar": ["notify", "notification"],
    "tiempo": ["time", "weather"],
    "hora": ["time", "current"],
    "web": ["fetch", "url", "web"],
    "página": ["page", "fetch", "web", "url"],
    "servidor": ["server", "list", "get"],
    "servidores": ["server", "servers", "list", "get"],
    "coolify": ["coolify", "server", "servers", "application", "deployment"],
    "contacto": ["contact", "contacts", "address"],
    "correo": ["mail", "email", "message"],
    "receta": ["recipe", "cookbook", "cook"],
    "cocinar": ["recipe", "cookbook"],
    "deck": ["deck", "board", "card", "kanban"],
    "noticias": ["news", "feed", "rss"],
    "feeds": ["news", "feed", "rss"],
    "chat": ["talk", "message", "conversation"],
    "mensaje": ["message", "talk", "send"],
    # Días de la semana
    "lunes": ["monday", "calendar", "event", "schedule"],
    "martes": ["tuesday", "calendar", "event", "schedule"],
    "miércoles": ["wednesday", "calendar", "event", "schedule"],
    "jueves": ["thursday", "calendar", "event", "schedule"],
    "viernes": ["friday", "calendar", "event", "schedule"],
    "sábado": ["saturday", "calendar", "event", "schedule"],
    "domingo": ["sunday", "calendar", "event", "schedule"],
    # Temporalidad
    "hoy": ["today", "current", "upcoming", "event", "calendar"],
    "mañana": ["tomorrow", "upcoming", "event", "calendar"],
    "ayer": ["yesterday", "event", "calendar"],
    "semana": ["week", "calendar", "event", "schedule"],
    "mes": ["month", "calendar", "event"],
    "año": ["year", "calendar"],
    "próximo": ["next", "upcoming", "schedule", "calendar"],
    "siguiente": ["next", "upcoming", "schedule"],
    "pasado": ["past", "last", "previous"],
    "fecha": ["date", "calendar", "event", "schedule"],
    # Entidades calendario
    "reunión": ["meeting", "event", "calendar", "create"],
    "cita": ["appointment", "event", "calendar"],
    "agenda": ["calendar", "event", "schedule", "list"],
    "recordatorio": ["reminder", "todo", "task"],
    "cumpleaños": ["birthday", "event", "calendar"],
    # Nextcloud específico
    "nextcloud": ["calendar", "event", "contact", "note", "file"],
    "nube": ["cloud", "nextcloud", "file", "webdav"],
}


def filter_tools_by_relevance(
    tools: list[dict[str, Any]],
    query: str,
    max_tools: int = 40,
) -> list[dict[str, Any]]:
    """Filter tools based on keyword relevance to the user's query.

    Always includes tools from small/system servers (dax-system), then
    fills the remaining budget with the best-scoring tools from other
    servers. Supports bilingual (ES/EN) queries via keyword expansion.
    """
    # Always include tools from privileged servers regardless of score.
    always: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("server_name") in _ALWAYS_INCLUDE_SERVERS:
            always.append(tool)
        else:
            candidates.append(tool)

    # If the total fits in the budget, return everything.
    if len(always) + len(candidates) <= max_tools:
        return always + candidates

    remaining_budget = max_tools - len(always)
    if remaining_budget <= 0:
        return always

    # Score candidates by keyword relevance.
    query_lower = query.lower()
    query_words = set(re.findall(r"\w+", query_lower))

    # Expand Spanish keywords to English equivalents.
    expanded_words = set(query_words)
    for word in query_words:
        if word in _ES_EN_KEYWORDS:
            expanded_words.update(_ES_EN_KEYWORDS[word])

    scored: list[tuple[float, dict[str, Any]]] = []
    for tool in candidates:
        server = tool.get("server_name", "").lower()
        name = tool.get("name", "").lower()
        description = tool.get("description", "").lower()
        tool_text = f"{server} {name} {description}"
        tool_words = set(re.findall(r"\w+", tool_text))

        word_matches = len(expanded_words & tool_words)
        # Server-name match: "Coolify", "Nextcloud", etc. should strongly
        # prefer tools from that server even if individual tool names vary.
        server_bonus = 10.0 if any(w in server for w in query_words) else 0.0
        # Name-match bonus: if any query word appears in the tool name
        name_bonus = 3.0 if any(w in name for w in expanded_words) else 0.0
        # Description bonus: partial substring match for short query words
        desc_bonus = sum(
            1.0 for w in expanded_words if len(w) >= 4 and w in description
        )
        score = word_matches + server_bonus + name_bonus + desc_bonus

        scored.append((score, tool))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [tool for _, tool in scored[:remaining_budget]]
    return always + top
