"""Login / logout / session-status endpoints.

These are intentionally NOT behind ``require_auth`` — they're how the user
obtains a session in the first place. Brute-force is mitigated by argon2's
cost and a small constant delay on failure.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from dax.web.dependencies import AuthDep, ConfigDep, SecretStoreDep

router = APIRouter(tags=["auth"])

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    password: str


class SetupRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    ok: bool


class AuthStatus(BaseModel):
    auth_enabled: bool
    configured: bool
    authenticated: bool


@router.get("/auth/status", response_model=AuthStatus)
async def auth_status(request: Request, auth: AuthDep) -> AuthStatus:
    return AuthStatus(
        auth_enabled=auth.enabled,
        configured=auth.configured,
        authenticated=auth.is_authenticated(request),
    )


@router.post("/auth/setup", response_model=LoginResponse)
async def setup(
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
    from dax.web.auth import hash_password

    if auth.configured:
        response.status_code = 409
        return LoginResponse(ok=False)

    if len(body.password) < 8:
        response.status_code = 400
        return LoginResponse(ok=False)

    new_hash = hash_password(body.password)

    # Persist encrypted, then update the live config + auth manager in place.
    store.set("DAX_SECURITY__PASSWORD_HASH", new_hash)

    object.__setattr__(config.security, "password_hash", new_hash)
    object.__setattr__(config.security, "auth_enabled", True)
    auth._password_hash = new_hash
    auth._enabled = True

    token = auth.issue_token()
    auth.set_cookie(response, token)
    logger.info("First-run account created and signed in")
    return LoginResponse(ok=True)


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: Request, body: LoginRequest, response: Response, auth: AuthDep
) -> LoginResponse:
    if not auth.enabled:
        return LoginResponse(ok=True)

    if not auth.verify_login(body.password):
        # Constant-ish delay to blunt online guessing.
        await asyncio.sleep(0.5)
        response.status_code = 401
        logger.warning("Failed login attempt from %s", request.client)
        return LoginResponse(ok=False)

    token = auth.issue_token()
    auth.set_cookie(response, token)
    logger.info("Successful login")
    return LoginResponse(ok=True)


@router.post("/auth/logout", response_model=LoginResponse)
async def logout(response: Response, auth: AuthDep) -> LoginResponse:
    auth.clear_cookie(response)
    return LoginResponse(ok=True)
