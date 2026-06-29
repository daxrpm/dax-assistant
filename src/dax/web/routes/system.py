"""System status & discovery endpoints — status, voice toggle, logs, audit,
tool policy, and LLM/Ollama model discovery. Read-mostly; no config mutation."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from dax.web.dependencies import ConfigDep

router = APIRouter(tags=["system"])


class StatusResponse(BaseModel):
    name: str
    version: str
    status: str
    voice_listening: bool
    llm_provider: str
    mcp_servers: int
    mcp_tools: int


class ToggleRequest(BaseModel):
    enabled: bool


class ToggleResponse(BaseModel):
    voice_listening: bool


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request, config: ConfigDep) -> StatusResponse:
    """Get the current system status."""
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    tool_count = mcp_manager.registry.tool_count if mcp_manager else 0
    return StatusResponse(
        name=config.name,
        version="0.1.0",
        status="running",
        voice_listening=request.app.state.voice_listening,
        llm_provider=config.llm.default_provider,
        mcp_servers=len(config.mcp.servers),
        mcp_tools=tool_count,
    )


@router.post("/voice/toggle", response_model=ToggleResponse)
async def toggle_voice(request: Request, body: ToggleRequest) -> ToggleResponse:
    """Toggle voice listening on or off."""
    request.app.state.voice_listening = body.enabled
    return ToggleResponse(voice_listening=body.enabled)


@router.get("/logs")
async def get_logs(request: Request, limit: int = 200) -> list[dict[str, Any]]:
    """Return recent backend log records (oldest first)."""
    buffer = getattr(request.app.state, "log_buffer", None)
    if buffer is None:
        return []
    return buffer.recent(limit=limit)


@router.get("/mcp/status")
async def get_mcp_status(request: Request) -> list[dict[str, Any]]:
    """Per-server MCP connection + tool status."""
    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is None:
        return []
    return manager.server_status()


@router.get("/tools/audit")
async def get_tool_audit(request: Request, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent tool-execution audit entries (newest first)."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        return []
    return await repo.get_tool_audit(limit=limit)


@router.get("/tools/policy")
async def get_tool_policy(config: ConfigDep) -> dict[str, Any]:
    """Expose the current tool policy so the UI can show what's gated."""
    policy = config.tools.policy
    return {
        "default": policy.default,
        "allow": policy.allow,
        "ask": policy.ask,
        "deny": policy.deny,
        "confirm_timeout_seconds": config.tools.confirm_timeout_seconds,
    }


@router.get("/ollama/models")
async def list_ollama_models(config: ConfigDep) -> list[dict[str, Any]]:
    """List models available in the local Ollama instance."""
    base_url = config.llm.ollama.base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                {
                    "name": m["name"],
                    "size_gb": round(m.get("size", 0) / 1e9, 1),
                    "modified": m.get("modified_at", ""),
                    "family": m.get("details", {}).get("family", ""),
                    "parameters": m.get("details", {}).get("parameter_size", ""),
                    "quantization": m.get("details", {}).get("quantization_level", ""),
                }
                for m in data.get("models", [])
            ]
    except Exception:
        return []


@router.get("/llm/models")
async def list_llm_models(config: ConfigDep, provider: str = "") -> dict[str, list[str]]:
    """Return available model IDs for each configured provider.

    Query param ``provider`` limits the response to a single provider.
    """
    results: dict[str, list[str]] = {}

    async def _openai() -> list[str]:
        key = config.llm.openai.api_key or ""
        base = (config.llm.openai.base_url or "https://api.openai.com/v1").rstrip("/")
        if not key:
            return []
        async with aiohttp.ClientSession() as session, session.get(
            f"{base}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 200:
                return []
            data = await r.json()
        return sorted(
            {m["id"] for m in data.get("data", []) if "gpt" in m.get("id", "").lower()},
        )

    async def _anthropic() -> list[str]:
        key = config.llm.anthropic.api_key or ""
        if not key:
            return []
        async with aiohttp.ClientSession() as session, session.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 200:
                return []
            data = await r.json()
        return sorted(m["id"] for m in data.get("data", []))

    async def _gemini() -> list[str]:
        key = config.llm.gemini.api_key or ""
        if not key:
            return []
        async with aiohttp.ClientSession() as session, session.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=1000",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 200:
                return []
            data = await r.json()
        return sorted(
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        )

    async def _ollama() -> list[str]:
        base = (config.llm.ollama.base_url or "http://localhost:11434").rstrip("/")
        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"{base}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                if r.status != 200:
                    return []
                data = await r.json()
            return sorted(m["name"] for m in data.get("models", []))
        except Exception:
            return []

    async def _deepseek() -> list[str]:
        from dax.llm.factory import _resolve_env

        ds = getattr(config.llm, "deepseek", None)
        if ds is None:
            return []
        key = _resolve_env(ds.api_key) or ds.api_key
        base = (ds.base_url or "https://api.deepseek.com").rstrip("/")
        if not key:
            return []
        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return []
                data = await r.json()
            return sorted(m["id"] for m in data.get("data", []))
        except Exception:
            return []

    targets = {
        "openai": _openai,
        "anthropic": _anthropic,
        "gemini": _gemini,
        "ollama": _ollama,
        "deepseek": _deepseek,
    }
    chosen = {provider: targets[provider]} if provider in targets else targets

    fetched = await asyncio.gather(
        *[fn() for fn in chosen.values()], return_exceptions=True
    )
    for prov, res in zip(chosen.keys(), fetched):
        results[prov] = res if isinstance(res, list) else []

    return results
