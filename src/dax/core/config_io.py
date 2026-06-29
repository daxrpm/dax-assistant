"""Configuration persistence — serialize :class:`DaxConfig` back to TOML.

This replaces ~210 lines of hand-built TOML strings that silently dropped any
field not explicitly listed. Serialization is now driven by Pydantic's
``model_dump()``, so **every** config field round-trips by construction — adding
a field to the model is enough; no parallel writer to update.

Secrets never land in the TOML file. The :data:`SECRET_FIELDS` table declares,
for each secret field, the env-var name it is stored under and how it is
referenced:

- ``REF``  — value is persisted to the :class:`SecretStore` and the TOML keeps a
  ``{env:VAR}`` placeholder (resolved at use-time by ``factory._resolve_env``).
- ``OMIT`` — value is persisted to the store and the field is removed from TOML
  entirely; it comes back through ``os.environ`` → pydantic-settings on reload
  (used for ``DAX_*`` nested env vars the SDKs/settings read directly).

Sensitive MCP headers (Authorization, X-Api-Key, …) are detected by name/value
and extracted to the store the same way, keyed deterministically per server.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING, Any

import tomli_w

if TYPE_CHECKING:
    from pathlib import Path

    from dax.core.config import DaxConfig
    from dax.storage.secrets import SecretStore


class SecretMode(Enum):
    """How a secret field is represented in the persisted TOML."""

    REF = "ref"  # keep a {env:VAR} placeholder in TOML
    OMIT = "omit"  # drop from TOML; reload via os.environ


# Dotted config paths that carry secrets → (env var name, mode). The single
# source of truth for "what is a secret and where does it live". Adding a secret
# field means adding one line here.
SECRET_FIELDS: dict[str, tuple[str, SecretMode]] = {
    "llm.anthropic.api_key": ("ANTHROPIC_API_KEY", SecretMode.REF),
    "llm.openai.api_key": ("OPENAI_API_KEY", SecretMode.REF),
    "llm.gemini.api_key": ("GEMINI_API_KEY", SecretMode.REF),
    "llm.deepseek.api_key": ("DEEPSEEK_API_KEY", SecretMode.REF),
    "telegram.bot_token": ("DAX_TELEGRAM__BOT_TOKEN", SecretMode.OMIT),
    "whatsapp.evolution_api_key": ("DAX_WHATSAPP__EVOLUTION_API_KEY", SecretMode.OMIT),
    "whatsapp.webhook_secret": ("DAX_WHATSAPP__WEBHOOK_SECRET", SecretMode.OMIT),
    "security.password_hash": ("DAX_SECURITY__PASSWORD_HASH", SecretMode.OMIT),
    "security.session_secret": ("DAX_SECURITY__SESSION_SECRET", SecretMode.OMIT),
}

# Top-level scalar fields live under a ``[general]`` table in the TOML, while
# the nested sub-models (voice, llm, …) are their own tables. Mirrors the read
# side (``config._flatten_toml``), which merges ``[general]`` to the top level.
_GENERAL_TABLE = "general"

# Header names that carry secrets and must never land in the TOML file.
_SENSITIVE_HEADER_NAMES: frozenset[str] = frozenset({
    "authorization", "x-api-key", "api-key", "x-token", "token",
    "x-auth-token", "x-access-token", "x-secret", "x-session",
    "cookie", "x-password", "x-bearer",
})


def _is_sensitive_header(name: str, value: str) -> bool:
    """Return True if this header likely carries a secret credential."""
    if name.lower().strip() in _SENSITIVE_HEADER_NAMES:
        return True
    # Also catch Bearer / Token / Basic auth regardless of header name.
    return value.strip().lower().startswith(("bearer ", "token ", "basic "))


def _env_var_for_header(server_name: str, header_name: str) -> str:
    """Build a deterministic env-var name for a sensitive MCP header.

    Example: server "coolify", header "Authorization"
             → DAX_MCP_COOLIFY_HDR_AUTHORIZATION
    """
    s = re.sub(r"[^a-z0-9]", "_", server_name.lower())
    h = re.sub(r"[^a-z0-9]", "_", header_name.lower())
    return f"DAX_MCP_{s.upper()}_HDR_{h.upper()}"


def secure_headers(
    server_name: str,
    headers: dict[str, str],
    store: SecretStore,
) -> dict[str, str]:
    """Return a headers dict safe to write to TOML.

    Sensitive values that are NOT already ``{env:…}`` references are extracted to
    the encrypted secret store and replaced with a ``{env:…}`` reference. The
    value is also exported to the process env (via ``store.set``) so the server
    can connect immediately without a restart.
    """
    safe: dict[str, str] = {}
    for name, value in headers.items():
        if value.startswith("{env:") or not _is_sensitive_header(name, value):
            safe[name] = value
        else:
            var = _env_var_for_header(server_name, name)
            store.set(var, value)
            safe[name] = f"{{env:{var}}}"
    return safe


def _get_path(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _del_path(data: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    cur: Any = data
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return
        cur = cur[part]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur: Any = data
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _strip_none(value: Any) -> Any:
    """Recursively drop None values — tomli_w cannot serialize them."""
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(v) for v in value]
    return value


def _extract_secrets(data: dict[str, Any], store: SecretStore) -> None:
    """Persist secret values to the store and rewrite/remove them in ``data``."""
    for path, (var, mode) in SECRET_FIELDS.items():
        value = _get_path(data, path)
        if not value:
            # Empty/unset secret: never write an empty placeholder.
            _del_path(data, path)
            continue
        if not str(value).startswith("{env:"):
            store.set(var, str(value))
        if mode is SecretMode.REF:
            _set_path(data, path, f"{{env:{var}}}")
        else:  # OMIT
            _del_path(data, path)


def _restructure(data: dict[str, Any]) -> dict[str, Any]:
    """Move top-level scalar fields under a ``[general]`` table.

    Nested sub-models (dict values) stay as their own top-level tables.
    """
    general: dict[str, Any] = {}
    tables: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            tables[key] = value
        else:
            general[key] = value
    return {_GENERAL_TABLE: general, **tables}


def dump_config_toml(
    config: DaxConfig,
    store: SecretStore,
    config_path: Path,
) -> None:
    """Serialize ``config`` to TOML at ``config_path``, extracting all secrets.

    Standalone (no HTTP request) so the app can persist outside a handler — e.g.
    when the agent saves a newly approved shell command.
    """
    data: dict[str, Any] = config.model_dump(mode="python")

    _extract_secrets(data, store)

    # Sensitive MCP headers → store + {env:…} refs.
    servers = (data.get("mcp") or {}).get("servers") or {}
    for name, srv in servers.items():
        srv["headers"] = secure_headers(name, srv.get("headers") or {}, store)

    structured = _restructure(_strip_none(data))

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(tomli_w.dumps(structured), encoding="utf-8")


# Backwards-compatible alias: the previous public name for this function.
write_config_toml = dump_config_toml
