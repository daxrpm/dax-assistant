"""Typed FastAPI dependencies — the single, explicit wiring surface.

Replaces scattered ``getattr(request.app.state, "thing", None)`` service-locator
lookups with declared, type-checked providers. Components are still held on
``app.state`` (set in :mod:`dax.app`), but every read goes through one of these
providers, so:

- routes declare exactly what they need (``mgr: McpManagerDep``),
- missing components fail with a clear ``503`` instead of a late ``AttributeError``
  or a silent ``None``,
- mypy sees real types at the call sites.

WebSocket handlers can't use ``Depends`` the same way, so the ``*_from_app``
helpers expose the same lookups for them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, status

# These are imported at runtime (not under TYPE_CHECKING) because the Annotated
# dependency aliases below embed them as real types — FastAPI resolves the
# annotations via get_type_hints() at startup, so the names must exist at runtime.
from dax.core.config import DaxConfig
from dax.core.policy import ToolPolicy
from dax.core.shell_allow import ShellAllowlist
from dax.llm.router import LLMRouter
from dax.mcp.manager import MCPManager
from dax.orchestrator.approval import ApprovalManager
from dax.orchestrator.bus import MessageBus
from dax.storage.repository import ConversationRepository
from dax.storage.secrets import SecretStore
from dax.web.auth import AuthManager

if TYPE_CHECKING:
    from starlette.applications import Starlette

    from dax.core.logbuffer import LogBuffer


def _require(app: Starlette, key: str, label: str) -> object:
    """Return ``app.state.<key>`` or raise 503 if it isn't wired yet."""
    value = getattr(app.state, key, None)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{label} is not available",
        )
    return value


# --- Always-present core components (set eagerly / in lifespan) ---


def get_config(request: Request) -> DaxConfig:
    return request.app.state.config  # type: ignore[no-any-return]


def get_bus(request: Request) -> MessageBus:
    return request.app.state.bus  # type: ignore[no-any-return]


def get_auth(request: Request) -> AuthManager:
    return request.app.state.auth  # type: ignore[no-any-return]


def get_secret_store(request: Request) -> SecretStore:
    """The encrypted secret store, falling back to one built from config.

    The fallback keeps endpoints working under TestClient / before the app has
    attached the live store to ``app.state``.
    """
    store = getattr(request.app.state, "secret_store", None)
    if isinstance(store, SecretStore):
        return store
    return SecretStore(request.app.state.config.storage.database_path)


# --- Optionally-wired adapters (required at runtime, 503 if absent) ---


def get_mcp_manager(request: Request) -> MCPManager:
    return _require(request.app, "mcp_manager", "MCP manager")  # type: ignore[return-value]


def get_repository(request: Request) -> ConversationRepository:
    return _require(request.app, "repository", "Conversation storage")  # type: ignore[return-value]


def get_llm_router(request: Request) -> LLMRouter:
    return _require(request.app, "llm_router", "LLM router")  # type: ignore[return-value]


def get_tool_policy(request: Request) -> ToolPolicy:
    return _require(request.app, "tool_policy", "Tool policy")  # type: ignore[return-value]


def get_shell_allow(request: Request) -> ShellAllowlist:
    return _require(request.app, "shell_allow", "Shell allowlist")  # type: ignore[return-value]


def get_approval(request: Request) -> ApprovalManager:
    return _require(request.app, "approval", "Approval manager")  # type: ignore[return-value]


# --- WebSocket / lifecycle helpers (no Depends available) ---


def auth_from_app(app: Starlette) -> AuthManager | None:
    return getattr(app.state, "auth", None)


def bus_from_app(app: Starlette) -> MessageBus | None:
    return getattr(app.state, "bus", None)


def approval_from_app(app: Starlette) -> ApprovalManager | None:
    return getattr(app.state, "approval", None)


def log_buffer_from_app(app: Starlette) -> LogBuffer | None:
    return getattr(app.state, "log_buffer", None)


# --- Annotated aliases for ergonomic route signatures ---

ConfigDep = Annotated[DaxConfig, Depends(get_config)]
BusDep = Annotated[MessageBus, Depends(get_bus)]
AuthDep = Annotated[AuthManager, Depends(get_auth)]
SecretStoreDep = Annotated[SecretStore, Depends(get_secret_store)]
McpManagerDep = Annotated[MCPManager, Depends(get_mcp_manager)]
RepositoryDep = Annotated[ConversationRepository, Depends(get_repository)]
LLMRouterDep = Annotated[LLMRouter, Depends(get_llm_router)]
ToolPolicyDep = Annotated[ToolPolicy, Depends(get_tool_policy)]
ShellAllowDep = Annotated[ShellAllowlist, Depends(get_shell_allow)]
ApprovalDep = Annotated[ApprovalManager, Depends(get_approval)]
