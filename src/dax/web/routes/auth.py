"""Login / logout / session-status endpoints.

These are intentionally NOT behind ``require_auth`` — they're how the user
obtains a session in the first place. Brute-force is mitigated by argon2's
cost and a small constant delay on failure.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from dax.web.auth import hash_password
from dax.web.dependencies import AuthDep, ConfigDep, SecretStoreDep

router = APIRouter(tags=["auth"])

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    password: str = Field(max_length=1024)


class SetupRequest(BaseModel):
    password: str = Field(max_length=1024)


class LoginResponse(BaseModel):
    """Result of a login/setup/logout call.

    ``token`` carries the signed session token on success. The browser SPA
    ignores it and relies on the ``Set-Cookie`` header; native clients (the
    desktop app) store it and send ``Authorization: Bearer <token>`` on HTTP
    requests and ``?token=<token>`` on WebSocket handshakes, because a
    ``SameSite=lax`` cookie is not reliably replayed from a webview's custom
    protocol origin.
    """

    ok: bool
    token: str | None = None
    # Why a rejection happened, when the reason is something the operator can
    # act on. A bare 403 on first-run setup left no way to tell "you are on the
    # wrong machine" apart from "the server is broken".
    detail: str | None = None


class AuthStatus(BaseModel):
    auth_enabled: bool
    configured: bool
    authenticated: bool


class HealthResponse(BaseModel):
    status: str
    instance_id: str
    role: str
    api_protocol: str
    api_version: int
    liveness: bool
    readiness: bool


def _client_key(request: Request) -> str:
    return request.client.host if request.client is not None else "<unknown>"


def _limit_attempts(
    request: Request,
    auth: AuthDep,
    scope: str,
    *,
    client_limit: int,
    global_limit: int,
) -> None:
    retry_after = auth.attempt_limiter.check(
        scope,
        _client_key(request),
        client_limit=client_limit,
        global_limit=global_limit,
    )
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts",
            headers={"Retry-After": str(retry_after)},
        )


def _is_loopback_request(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ipaddress.ip_address(request.client.host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Public identity, liveness, and readiness for trusted client probing."""
    ready = bool(getattr(request.app.state, "ready", False))
    return HealthResponse(
        status="ok" if ready else "starting",
        instance_id=request.app.state.server_instance_id,
        role="authoritative",
        api_protocol="dax",
        api_version=1,
        liveness=True,
        readiness=ready,
    )


@router.get("/auth/status", response_model=AuthStatus)
async def auth_status(request: Request, auth: AuthDep) -> AuthStatus:
    return AuthStatus(
        auth_enabled=auth.enabled,
        configured=auth.configured,
        authenticated=auth.is_authenticated(request),
    )


@router.post("/auth/setup", response_model=LoginResponse)
async def setup(
    request: Request,
    body: SetupRequest,
    response: Response,
    auth: AuthDep,
    store: SecretStoreDep,
    config: ConfigDep,
) -> LoginResponse:
    """First-run account creation — set the login password and sign in.

    Public on purpose, but only usable while no password exists yet (i.e. the
    very first boot). The password hash is stored encrypted in SQLite (never in
    .env), and the user is logged in immediately. After this, the endpoint is a
    no-op 409 so it can't be used to reset an existing account.
    """
    if not _is_loopback_request(request):
        response.status_code = 403
        return LoginResponse(
            ok=False,
            detail=(
                "The first account can only be created from the machine running the "
                "backend, so an unclaimed backend cannot be taken over from the "
                "network. Run `dax claim` over SSH on the server, or re-run the "
                "installer, then sign in from here."
            ),
        )

    _limit_attempts(request, auth, "setup", client_limit=5, global_limit=20)

    if len(body.password) < 8:
        response.status_code = 400
        return LoginResponse(
            ok=False, detail="The password must be at least 8 characters."
        )

    async with auth.setup_lock:
        if auth.configured:
            response.status_code = 409
            return LoginResponse(
                ok=False,
                detail=(
                    "This backend already has an account. Sign in with its password "
                    "instead."
                ),
            )

        new_hash = await asyncio.to_thread(hash_password, body.password)

        # Persist encrypted, then update the live config + auth manager in place.
        store.set("DAX_SECURITY__PASSWORD_HASH", new_hash)

        object.__setattr__(config.security, "password_hash", new_hash)
        object.__setattr__(config.security, "auth_enabled", True)
        auth._password_hash = new_hash
        auth._enabled = True

        token = auth.issue_token()
        auth.set_cookie(response, token)
        logger.info("First-run account created and signed in")
        return LoginResponse(ok=True, token=token)


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: Request, body: LoginRequest, response: Response, auth: AuthDep
) -> LoginResponse:
    if not auth.enabled:
        return LoginResponse(ok=True)

    _limit_attempts(request, auth, "login", client_limit=5, global_limit=30)

    if not await asyncio.to_thread(auth.verify_login, body.password):
        # Constant-ish delay to blunt online guessing.
        await asyncio.sleep(0.5)
        response.status_code = 401
        logger.warning("Failed login attempt from %s", request.client)
        return LoginResponse(ok=False)

    token = auth.issue_token()
    auth.set_cookie(response, token)
    logger.info("Successful login")
    return LoginResponse(ok=True, token=token)


@router.post("/auth/logout", response_model=LoginResponse)
async def logout(response: Response, auth: AuthDep) -> LoginResponse:
    auth.clear_cookie(response)
    return LoginResponse(ok=True)
