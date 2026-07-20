"""Device enrolment, access tokens, and revocation.

The password is the human's credential; a device secret is a client's. The
phone never learns the password: an already-authenticated client (desktop or
browser) mints a short-lived pairing code, the phone redeems it once for a
device secret, and from then on exchanges that secret for access tokens that
expire in minutes.

The endpoints split three ways by design:

* ``/auth/devices/pair`` requires an existing session — only someone who is
  already in may invite a new device.
* ``/auth/devices/enroll`` and ``/auth/devices/token`` are public, because a
  device that has no credential yet cannot present one. They are guarded by
  the one-time code and the device secret respectively.
* Listing and revocation require a session, so a compromised device cannot
  enumerate or unenroll its siblings.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from dax.storage.devices import (
    CAPABILITY_NODE_KIND,
    CLIENT_KIND,
    DEVICE_KINDS,
    generate_pairing_code,
)
from dax.web.auth import AuthManager, require_session
from dax.web.dependencies import AuthDep, ConfigDep

router = APIRouter(tags=["devices"])

logger = logging.getLogger(__name__)

# Only ever a couple of codes outstanding in practice; the cap stops an
# authenticated-but-buggy client from growing the table without bound.
_MAX_OUTSTANDING_CODES = 8


@dataclass(slots=True)
class _PairingCode:
    code: str
    expires_at: float
    kind: str


class _PairingCodes:
    """One-time, expiring pairing codes held in memory.

    Deliberately not persisted: a code that does not survive a restart is one
    fewer credential at rest, and the window is minutes.
    """

    def __init__(self) -> None:
        self._codes: list[_PairingCode] = []

    def issue(self, ttl_seconds: int, kind: str = CLIENT_KIND) -> _PairingCode:
        self._prune()
        if len(self._codes) >= _MAX_OUTSTANDING_CODES:
            self._codes.pop(0)
        entry = _PairingCode(
            code=generate_pairing_code(), expires_at=time.time() + ttl_seconds, kind=kind
        )
        self._codes.append(entry)
        return entry

    def redeem(self, code: str) -> str | None:
        """Consume *code*. A code works exactly once."""
        self._prune()
        normalized = code.strip().upper()
        for entry in self._codes:
            if entry.code == normalized:
                self._codes.remove(entry)
                return entry.kind
        return None

    def _prune(self) -> None:
        now = time.time()
        self._codes = [entry for entry in self._codes if entry.expires_at > now]

    @property
    def outstanding(self) -> int:
        self._prune()
        return len(self._codes)


def _codes(request: Request) -> _PairingCodes:
    codes = getattr(request.app.state, "pairing_codes", None)
    if codes is None:
        codes = _PairingCodes()
        request.app.state.pairing_codes = codes
    return codes


class PairResponse(BaseModel):
    code: str
    expires_in_seconds: int
    pairing_uri: str
    backend_url: str
    kind: str


class PairRequest(BaseModel):
    model_config = {"extra": "forbid"}

    kind: str = CLIENT_KIND


class EnrollRequest(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(default="", max_length=64)
    platform: str = Field(default="", max_length=32)


class EnrollResponse(BaseModel):
    """The only response that ever carries the plaintext device secret."""

    ok: bool
    device_id: str | None = None
    device_secret: str | None = None
    instance_id: str | None = None


class TokenRequest(BaseModel):
    device_id: str = Field(max_length=128)
    device_secret: str = Field(max_length=256)


class TokenResponse(BaseModel):
    ok: bool
    token: str | None = None
    expires_in_seconds: int | None = None


class DeviceListResponse(BaseModel):
    devices: list[dict[str, object]]


class OkResponse(BaseModel):
    ok: bool


def _limit_attempts(
    request: Request,
    auth: AuthManager,
    scope: str,
    *,
    client_limit: int,
    global_limit: int,
) -> None:
    client_key = request.client.host if request.client is not None else "<unknown>"
    retry_after = auth.attempt_limiter.check(
        scope,
        client_key,
        client_limit=client_limit,
        global_limit=global_limit,
    )
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts",
            headers={"Retry-After": str(retry_after)},
        )


@router.post(
    "/auth/devices/pair",
    response_model=PairResponse,
    dependencies=[Depends(require_session)],
)
async def pair_device(
    request: Request,
    config: ConfigDep,
    auth: AuthDep,
    body: PairRequest | None = None,
) -> PairResponse:
    """Mint a one-time pairing code for a new device."""
    _limit_attempts(request, auth, "device_pair", client_limit=10, global_limit=50)
    ttl = max(60, config.security.pairing_code_ttl_minutes * 60)
    body = body or PairRequest()
    if body.kind not in DEVICE_KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid device kind")
    entry = _codes(request).issue(ttl, body.kind)
    backend_url = str(request.base_url).rstrip("/")
    pairing_uri = f"dax://pair?{urlencode({'url': backend_url, 'code': entry.code})}"
    logger.info("Issued a device pairing code (expires in %ds)", ttl)
    return PairResponse(
        code=entry.code,
        expires_in_seconds=ttl,
        pairing_uri=pairing_uri,
        backend_url=backend_url,
        kind=entry.kind,
    )


@router.post("/auth/devices/enroll", response_model=EnrollResponse)
async def enroll_device(
    request: Request, body: EnrollRequest, response: Response, auth: AuthDep
) -> EnrollResponse:
    """Redeem a pairing code for a device credential. Public, code-gated."""
    devices = auth.devices
    if devices is None:
        response.status_code = 503
        return EnrollResponse(ok=False)

    _limit_attempts(request, auth, "device_enroll", client_limit=10, global_limit=50)

    kind = _codes(request).redeem(body.code)
    if kind is None:
        # Same delay as a failed login: the code space is small enough that
        # online guessing is the realistic attack.
        await asyncio.sleep(0.5)
        response.status_code = 401
        logger.warning("Rejected device enrolment with an invalid pairing code")
        return EnrollResponse(ok=False)

    device, secret = await devices.enroll(
        name=body.name or "Unnamed device",
        platform=body.platform or "unknown",
        kind=kind,
    )
    return EnrollResponse(
        ok=True,
        device_id=device.id,
        device_secret=secret,
        instance_id=request.app.state.server_instance_id,
    )


@router.post("/auth/devices/token", response_model=TokenResponse)
async def issue_device_token(
    request: Request, body: TokenRequest, response: Response, auth: AuthDep
) -> TokenResponse:
    """Exchange a device secret for a short-lived access token."""
    devices = auth.devices
    if devices is None:
        response.status_code = 503
        return TokenResponse(ok=False)

    _limit_attempts(request, auth, "device_token", client_limit=10, global_limit=100)

    if not await asyncio.to_thread(devices.verify_secret, body.device_id, body.device_secret):
        await asyncio.sleep(0.5)
        response.status_code = 401
        logger.warning("Rejected token request for device %s", body.device_id)
        return TokenResponse(ok=False)

    await devices.touch(body.device_id)
    kind = devices.kind_of(body.device_id)
    token = (
        auth.issue_capability_token(body.device_id)
        if kind == CAPABILITY_NODE_KIND
        else auth.issue_device_token(body.device_id)
    )
    return TokenResponse(
        ok=True,
        token=token,
        expires_in_seconds=auth.device_token_ttl_seconds,
    )


@router.get(
    "/auth/devices",
    response_model=DeviceListResponse,
    dependencies=[Depends(require_session)],
)
async def list_devices(auth: AuthDep) -> DeviceListResponse:
    devices = auth.devices
    if devices is None:
        return DeviceListResponse(devices=[])

    # Live presence, not just "when it last asked for a token". The desktop
    # shows the phone as attached only while a socket is actually open.
    from dax.web.routes.chat import ws_manager

    connected = ws_manager.connected_device_ids
    hub = getattr(auth, "capability_hub", None)
    payload: list[dict[str, object]] = []
    for device in await devices.list_devices():
        entry = device.to_json()
        entry["connected"] = (
            hub.is_present(device.id)
            if device.kind == CAPABILITY_NODE_KIND and hub is not None
            else device.id in connected
        )
        payload.append(entry)
    return DeviceListResponse(devices=payload)


@router.post(
    "/auth/devices/{device_id}/revoke",
    response_model=OkResponse,
    dependencies=[Depends(require_session)],
)
async def revoke_device(device_id: str, response: Response, auth: AuthDep) -> OkResponse:
    devices = auth.devices
    if devices is None or not await devices.revoke(device_id):
        response.status_code = 404
        return OkResponse(ok=False)
    hub = getattr(auth, "capability_hub", None)
    if hub is not None:
        await hub.disconnect_node(device_id)
    return OkResponse(ok=True)


@router.delete(
    "/auth/devices/{device_id}",
    response_model=OkResponse,
    dependencies=[Depends(require_session)],
)
async def delete_device(device_id: str, response: Response, auth: AuthDep) -> OkResponse:
    devices = auth.devices
    if devices is None or not await devices.delete(device_id):
        response.status_code = 404
        return OkResponse(ok=False)
    hub = getattr(auth, "capability_hub", None)
    if hub is not None:
        await hub.disconnect_node(device_id)
    return OkResponse(ok=True)
