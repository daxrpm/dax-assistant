"""MCP OAuth 2.1 authentication endpoints.

Implements the MCP Authorization spec (draft) for remote MCP servers
that require OAuth. Supports the full PKCE flow:

1. POST /api/mcp/{name}/auth/start → returns authorization URL
2. GET  /api/mcp/oauth/callback    → handles redirect from auth provider
3. GET  /api/mcp/{name}/auth/status → check if authenticated
4. POST /api/mcp/{name}/auth/logout → clear stored tokens

The flow discovers the authorization server from the MCP server's
Protected Resource Metadata (RFC 9728), generates PKCE parameters,
and exchanges the auth code for tokens.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from base64 import urlsafe_b64encode
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from dax.web.dependencies import ConfigDep

router = APIRouter(tags=["oauth"])

logger = logging.getLogger(__name__)

# In-memory pending auth flows (state → flow data)
# For production with multiple workers, use DB/Redis instead.
_pending_flows: dict[str, dict[str, Any]] = {}

# Token storage file
_TOKEN_FILE = Path("data/mcp-tokens.json")


# -- Public endpoints --


class _AuthStartResponse:
    """Not a Pydantic model to avoid import — just a dict."""


@router.post("/mcp/{name}/auth/start")
async def start_auth(name: str, request: Request, config: ConfigDep) -> dict[str, str]:
    """Start the OAuth flow for a remote MCP server.

    1. Hits the MCP server to get the WWW-Authenticate header
    2. Fetches Protected Resource Metadata
    3. Discovers the Authorization Server metadata
    4. Generates PKCE parameters
    5. Returns the authorization URL for the frontend to open
    """
    server_config = config.mcp.servers.get(name)

    if not server_config:
        raise HTTPException(404, f"MCP server '{name}' not configured")

    if server_config.transport not in ("streamable_http", "http", "sse"):
        raise HTTPException(400, "OAuth only works with HTTP transport servers")

    server_url = server_config.url
    if not server_url:
        raise HTTPException(400, f"MCP server '{name}' has no URL")

    # Step 1: Discover auth endpoints
    auth_info = await _discover_auth(server_url)
    if not auth_info:
        raise HTTPException(
            400,
            "Could not discover OAuth endpoints. "
            "The server may not support OAuth authentication.",
        )

    # Step 2: Determine redirect URI
    host = request.headers.get("host", "localhost:8420")
    scheme = request.headers.get("x-forwarded-proto", "http")
    redirect_uri = f"{scheme}://{host}/api/mcp/oauth/callback"

    # Step 3: Get or register client_id
    client_info = _load_client_info(name)
    if not client_info:
        # Try Dynamic Client Registration (RFC 7591)
        reg_endpoint = auth_info.get("registration_endpoint")
        if reg_endpoint:
            client_info = await _register_client(
                reg_endpoint, redirect_uri, name,
            )
            if client_info:
                _store_client_info(name, client_info)

    if not client_info or not client_info.get("client_id"):
        raise HTTPException(
            400,
            "Could not obtain client_id. The server may require "
            "manual OAuth app registration.",
        )

    # Step 4: Generate PKCE parameters
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_hex(16)

    # Step 5: Store flow data
    _pending_flows[state] = {
        "mcp_name": name,
        "server_url": server_url,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "token_endpoint": auth_info["token_endpoint"],
        "client_id": client_info["client_id"],
        "client_secret": client_info.get("client_secret", ""),
        "created_at": time.time(),
    }

    # Step 6: Build authorization URL
    params = {
        "response_type": "code",
        "client_id": client_info["client_id"],
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "redirect_uri": redirect_uri,
        "scope": auth_info.get("scope", ""),
        "resource": server_url,
    }

    auth_url = f"{auth_info['authorization_endpoint']}?{urlencode(params)}"

    logger.info("OAuth flow started for MCP server '%s'", name)
    return {"authorization_url": auth_url, "state": state}


@router.get("/mcp/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
) -> HTMLResponse:
    """Handle the OAuth redirect callback from the auth provider."""
    if error:
        logger.warning("OAuth error: %s — %s", error, error_description)
        return HTMLResponse(
            _callback_html(
                success=False,
                message=f"Authentication failed: {error_description or error}",
            ),
            status_code=400,
        )

    if not state or state not in _pending_flows:
        return HTMLResponse(
            _callback_html(success=False, message="Invalid or expired state."),
            status_code=400,
        )

    flow = _pending_flows.pop(state)

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            data: dict[str, str] = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": flow.get("client_id", ""),
                "redirect_uri": flow["redirect_uri"],
                "code_verifier": flow["code_verifier"],
            }
            if flow.get("client_secret"):
                data["client_secret"] = flow["client_secret"]

            resp = await client.post(
                flow["token_endpoint"],
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        try:
            tokens = resp.json()
        except Exception:
            tokens = {}

        if not tokens.get("access_token"):
            logger.error(
                "Token exchange failed (status %d): %s",
                resp.status_code, resp.text,
            )
            return HTMLResponse(
                _callback_html(
                    success=False,
                    message=f"Token exchange failed: {resp.status_code}",
                ),
                status_code=400,
            )
        _store_tokens(flow["mcp_name"], {
            "access_token": tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "token_type": tokens.get("token_type", "bearer"),
            "expires_at": time.time() + tokens.get("expires_in", 3600),
            "scope": tokens.get("scope", ""),
            "server_url": flow["server_url"],
        })

        logger.info(
            "OAuth tokens stored for MCP server '%s'", flow["mcp_name"],
        )

        # Reconnect the MCP server NOW so it picks up the fresh token without
        # requiring a restart (previously the token sat unused until reboot).
        await _reconnect_mcp_server(request, flow["mcp_name"])

        return HTMLResponse(_callback_html(success=True))

    except Exception:
        logger.exception("OAuth token exchange failed")
        return HTMLResponse(
            _callback_html(success=False, message="Token exchange failed."),
            status_code=500,
        )


@router.get("/mcp/{name}/auth/status")
async def auth_status(name: str) -> dict[str, Any]:
    """Check if a server has stored OAuth tokens."""
    tokens = _load_tokens(name)
    if not tokens:
        return {"authenticated": False}

    expired = tokens.get("expires_at", 0) < time.time()
    return {
        "authenticated": True,
        "expired": expired,
        "scope": tokens.get("scope", ""),
        "server_url": tokens.get("server_url", ""),
    }


@router.post("/mcp/{name}/auth/logout")
async def auth_logout(name: str) -> dict[str, str]:
    """Clear stored OAuth tokens for a server."""
    _delete_tokens(name)
    logger.info("OAuth tokens cleared for MCP server '%s'", name)
    return {"status": "ok"}


# -- Auth discovery --


async def _discover_auth(server_url: str) -> dict[str, str] | None:
    """Discover OAuth endpoints for a remote MCP server.

    Follows the MCP authorization spec:
    1. Hit the server, get 401 + WWW-Authenticate
    2. Fetch Protected Resource Metadata
    3. Fetch Authorization Server metadata
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Step 1: Try to connect, expect 401
            resp = await client.post(
                server_url,
                json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            )

            if resp.status_code == 401:
                www_auth = resp.headers.get("www-authenticate", "")
                return await _parse_www_authenticate(www_auth, client)

            # Some servers return 403 or redirect
            if resp.status_code in (403, 302, 307):
                # Try well-known endpoint
                return await _try_well_known(server_url, client)

    except Exception:
        logger.debug("Auth discovery failed for %s", server_url, exc_info=True)

    return None


async def _parse_www_authenticate(
    header: str, client: httpx.AsyncClient,
) -> dict[str, str] | None:
    """Parse WWW-Authenticate header and discover auth endpoints."""
    # Extract resource_metadata URL
    import re
    match = re.search(r'resource_metadata="([^"]+)"', header)
    if not match:
        return None

    metadata_url = match.group(1)

    # Fetch Protected Resource Metadata
    resp = await client.get(metadata_url)
    if resp.status_code != 200:
        return None

    resource_meta = resp.json()
    auth_servers = resource_meta.get("authorization_servers", [])
    if not auth_servers:
        return None

    # Fetch Authorization Server metadata
    as_url = auth_servers[0]
    as_meta = await _fetch_as_metadata(as_url, client)
    if not as_meta:
        return None

    return {
        "authorization_endpoint": as_meta.get("authorization_endpoint", ""),
        "token_endpoint": as_meta.get("token_endpoint", ""),
        "registration_endpoint": as_meta.get("registration_endpoint", ""),
        "scope": " ".join(resource_meta.get("scopes_supported", [])),
    }


async def _fetch_as_metadata(
    as_url: str, client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    """Fetch Authorization Server metadata via well-known endpoints."""
    from urllib.parse import urlparse

    parsed = urlparse(as_url)

    # Try OAuth AS metadata (RFC 8414)
    for well_known in [
        f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-authorization-server{parsed.path}",
        f"{as_url}/.well-known/openid-configuration",
        f"{parsed.scheme}://{parsed.netloc}/.well-known/openid-configuration",
    ]:
        try:
            resp = await client.get(well_known)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            continue

    return None


async def _try_well_known(
    server_url: str, client: httpx.AsyncClient,
) -> dict[str, str] | None:
    """Try to find OAuth metadata via well-known URL patterns."""
    from urllib.parse import urlparse

    parsed = urlparse(server_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    try:
        resp = await client.get(
            f"{base}/.well-known/oauth-protected-resource",
        )
        if resp.status_code == 200:
            return await _parse_www_authenticate(
                f'resource_metadata="{base}/.well-known/oauth-protected-resource"',
                client,
            )
    except Exception:
        pass

    return None


# -- Token storage --


def _store_tokens(name: str, tokens: dict[str, Any]) -> None:
    """Store OAuth tokens to disk (owner-read-only permissions)."""
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_tokens = _load_all_tokens()
    all_tokens[name] = tokens

    _TOKEN_FILE.write_text(json.dumps(all_tokens, indent=2))
    _TOKEN_FILE.chmod(0o600)


def _load_tokens(name: str) -> dict[str, Any] | None:
    """Load stored tokens for a specific server."""
    all_tokens = _load_all_tokens()
    return all_tokens.get(name)


def _delete_tokens(name: str) -> None:
    """Delete stored tokens for a server."""
    all_tokens = _load_all_tokens()
    all_tokens.pop(name, None)
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.write_text(json.dumps(all_tokens, indent=2))


def _load_all_tokens() -> dict[str, Any]:
    """Load all stored tokens from disk."""
    if not _TOKEN_FILE.exists():
        return {}
    try:
        return json.loads(_TOKEN_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def get_access_token(name: str) -> str | None:
    """Get the current access token for a server (used by MCP client)."""
    tokens = _load_tokens(name)
    if not tokens:
        return None

    if tokens.get("expires_at", 0) < time.time():
        logger.warning("OAuth token expired for '%s'", name)
        return None

    return tokens.get("access_token")


async def _reconnect_mcp_server(request: Request, name: str) -> None:
    """Reconnect an MCP server so a freshly stored token takes effect."""
    manager = getattr(request.app.state, "mcp_manager", None)
    config = getattr(request.app.state, "config", None)
    if manager is None or config is None:
        return
    server_config = config.mcp.servers.get(name)
    if server_config is None:
        return
    try:
        count = await manager.add_server(name, server_config)
        logger.info("Reconnected MCP server '%s' after auth (%d tools)", name, count)
    except Exception:
        logger.exception("Failed to reconnect MCP server '%s' after auth", name)


async def refresh_access_token(name: str) -> str | None:
    """Refresh an expired access token using the stored refresh_token.

    Returns the new access token, or None if refresh is impossible. Called
    best-effort before reconnecting an HTTP MCP server.
    """
    tokens = _load_tokens(name)
    if not tokens:
        return None
    # Still valid — nothing to do.
    if tokens.get("expires_at", 0) >= time.time() + 30:
        return tokens.get("access_token")

    refresh_token = tokens.get("refresh_token")
    client = _load_client_info(name)
    if not refresh_token or not client:
        return None

    # The token endpoint lives in the AS metadata; rediscover from server_url.
    auth_info = await _discover_auth(tokens.get("server_url", ""))
    if not auth_info or not auth_info.get("token_endpoint"):
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client.get("client_id", ""),
            }
            if client.get("client_secret"):
                data["client_secret"] = client["client_secret"]
            resp = await http.post(
                auth_info["token_endpoint"],
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        new = resp.json()
        if not new.get("access_token"):
            logger.warning("Token refresh failed for '%s': %s", name, resp.text[:200])
            return None
        tokens.update(
            {
                "access_token": new["access_token"],
                "refresh_token": new.get("refresh_token", refresh_token),
                "expires_at": time.time() + new.get("expires_in", 3600),
            }
        )
        _store_tokens(name, tokens)
        logger.info("Refreshed OAuth token for '%s'", name)
        return new["access_token"]
    except Exception:
        logger.exception("Token refresh error for '%s'", name)
        return None


# -- Dynamic Client Registration (RFC 7591) --

_CLIENT_FILE = Path("data/mcp-clients.json")


async def _register_client(
    registration_endpoint: str,
    redirect_uri: str,
    server_name: str,
) -> dict[str, Any] | None:
    """Register as an OAuth client via Dynamic Client Registration."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                registration_endpoint,
                json={
                    "client_name": f"Dax Assistant ({server_name})",
                    "redirect_uris": [redirect_uri],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "client_secret_post",
                },
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                logger.info(
                    "Registered OAuth client for '%s': %s",
                    server_name, data.get("client_id"),
                )
                return {
                    "client_id": data.get("client_id", ""),
                    "client_secret": data.get("client_secret", ""),
                    "registration_endpoint": registration_endpoint,
                }
            logger.warning(
                "Client registration failed for '%s': %s %s",
                server_name, resp.status_code, resp.text,
            )
    except Exception:
        logger.exception("Client registration error for '%s'", server_name)
    return None


def _store_client_info(name: str, info: dict[str, Any]) -> None:
    """Store registered client credentials to disk."""
    _CLIENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    all_clients = _load_all_clients()
    all_clients[name] = info
    _CLIENT_FILE.write_text(json.dumps(all_clients, indent=2))
    _CLIENT_FILE.chmod(0o600)


def _load_client_info(name: str) -> dict[str, Any] | None:
    """Load stored client credentials for a server."""
    return _load_all_clients().get(name)


def _load_all_clients() -> dict[str, Any]:
    """Load all stored client credentials from disk."""
    if not _CLIENT_FILE.exists():
        return {}
    try:
        return json.loads(_CLIENT_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


# -- HTML templates --


def _callback_html(success: bool, message: str = "") -> str:
    """Generate the callback page HTML."""
    if success:
        return """
        <!DOCTYPE html>
        <html><head><title>Dax - Auth Success</title>
        <style>body{font-family:system-ui;display:flex;justify-content:center;
        align-items:center;height:100vh;margin:0;background:#0f0f0f;color:#e0e0e0}
        .box{text-align:center}h1{color:#22c55e}
        </style></head><body><div class="box">
        <h1>Authenticated!</h1>
        <p>You can close this window and return to Dax.</p>
        <script>setTimeout(()=>window.close(),2000)</script>
        </div></body></html>
        """
    return f"""
    <!DOCTYPE html>
    <html><head><title>Dax - Auth Failed</title>
    <style>body{{font-family:system-ui;display:flex;justify-content:center;
    align-items:center;height:100vh;margin:0;background:#0f0f0f;color:#e0e0e0}}
    .box{{text-align:center}}h1{{color:#ef4444}}
    </style></head><body><div class="box">
    <h1>Authentication Failed</h1>
    <p>{message}</p>
    </div></body></html>
    """
