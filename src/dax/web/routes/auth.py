"""Login / logout / session-status endpoints.

These are intentionally NOT behind ``require_auth`` — they're how the user
obtains a session in the first place. Brute-force is mitigated by argon2's
cost and a small constant delay on failure.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

if TYPE_CHECKING:
    from dax.web.auth import AuthManager

router = APIRouter(tags=["auth"])

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    ok: bool


class AuthStatus(BaseModel):
    auth_enabled: bool
    configured: bool
    authenticated: bool


def _auth(request: Request) -> AuthManager:
    return request.app.state.auth


@router.get("/auth/status", response_model=AuthStatus)
async def auth_status(request: Request) -> AuthStatus:
    auth = _auth(request)
    return AuthStatus(
        auth_enabled=auth.enabled,
        configured=auth.configured,
        authenticated=auth.is_authenticated(request),
    )


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest, response: Response) -> LoginResponse:
    auth = _auth(request)
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
async def logout(request: Request, response: Response) -> LoginResponse:
    _auth(request).clear_cookie(response)
    return LoginResponse(ok=True)
