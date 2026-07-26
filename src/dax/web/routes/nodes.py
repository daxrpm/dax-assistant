"""Capability-node fleet: what each laptop is asked to do, and whether it is up.

Policy is configuration, so the backend owns it. A node reads its own entry when
it connects rather than keeping a local copy, which is what makes "stop
processing on the laptop" take effect from whichever client is in reach —
including the phone, through the restricted surface in ``mobile.py``.

Listing is deliberately richer than the stored policy: a policy nobody can see
the effect of is a policy nobody trusts, so every row carries live presence
taken from the hub rather than from the last time the node asked for a token.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from dax.capabilities.tickets import (
    DEFAULT_TTL_SECONDS,
    issue_ticket,
    public_key_for,
    signing_key,
)
from dax.core.config import NodePolicyConfig
from dax.storage.devices import CAPABILITY_NODE_KIND
from dax.web.dependencies import AuthDep, ConfigDep, SecretStoreDep, persist_config

router = APIRouter(tags=["nodes"])
# Ticket issue is device-authenticated: the phone asking is the whole point, and
# it has a device token rather than a session. Management stays session-only on
# `router`, so a phone still cannot enumerate or re-policy the fleet.
client_router = APIRouter(tags=["nodes"])
logger = logging.getLogger(__name__)


class NodePolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools_enabled: bool | None = None
    shell_enabled: bool | None = None
    process_locally: bool | None = None
    inference: str | None = None
    voice: str | None = None
    app_open_allow: list[str] | None = None


def _policy_json(policy: NodePolicyConfig) -> dict[str, Any]:
    return {
        "tools_enabled": policy.tools_enabled,
        "shell_enabled": policy.shell_enabled,
        "process_locally": policy.process_locally,
        "inference": policy.inference,
        "voice": policy.voice,
        "app_open_allow": policy.app_open_allow,
    }


async def node_fleet(request: Request, config: ConfigDep, auth: AuthDep) -> dict[str, Any]:
    """Fleet settings plus one row per enrolled capability node."""
    devices = auth.devices
    hub = getattr(request.app.state, "capability_hub", None)
    rows: list[dict[str, Any]] = []
    if devices is not None:
        for device in await devices.list_devices():
            if device.kind != CAPABILITY_NODE_KIND:
                continue
            rows.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "platform": device.platform,
                    "last_seen_at": device.last_seen_at,
                    "revoked": device.revoked,
                    "connected": hub.is_present(device.id) if hub is not None else False,
                    "endpoints": hub.endpoints_for(device.id) if hub is not None else [],
                    "policy": _policy_json(config.nodes.policy_for(device.id)),
                }
            )
    return {
        "enabled": config.nodes.enabled,
        "prefer_when_available": config.nodes.prefer_when_available,
        "nodes": rows,
    }


@router.get("/nodes")
async def get_nodes(request: Request, config: ConfigDep, auth: AuthDep) -> dict[str, Any]:
    return await node_fleet(request, config, auth)


@client_router.post("/nodes/{node_id}/session-ticket")
async def issue_session_ticket(
    request: Request,
    node_id: str,
    config: ConfigDep,
    auth: AuthDep,
    store: SecretStoreDep,
) -> dict[str, Any]:
    """Vouch for the calling device so it may open a session on *node_id*.

    Everything here is a refusal the node would otherwise have to make on worse
    information — it can check a signature, but it cannot know whether the fleet
    is switched off, whether this laptop is meant to host, or whether the phone
    asking has been revoked.
    """
    device_id = auth.requesting_device(request)
    if device_id is None:
        # A session credential is not a device. The desktop runs on the laptop
        # itself and has no reason to hand itself a ticket.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "A device credential is required for a node session"
        )

    devices = auth.devices
    if devices is None or not devices.is_active_kind(node_id, CAPABILITY_NODE_KIND):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown capability node")

    if not config.nodes.hosts_sessions(node_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This node is not configured to host sessions"
        )

    hub = getattr(request.app.state, "capability_hub", None)
    if hub is None or not hub.is_present(node_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "This node is not connected")

    key = signing_key(store)
    ticket = issue_ticket(key, node_id=node_id, device_id=device_id)
    logger.info("Issued a node session ticket for %s", node_id)
    return {
        "ticket": ticket,
        "expires_in_seconds": DEFAULT_TTL_SECONDS,
        "endpoints": hub.endpoints_for(node_id),
        # So a client can check the node's own proof of identity offline.
        "public_key": public_key_for(key),
    }


@router.patch("/nodes/{node_id}")
async def update_node_policy(
    request: Request, node_id: str, body: NodePolicyUpdate, config: ConfigDep, auth: AuthDep
) -> dict[str, Any]:
    """Update one node's policy.

    The node must be an enrolled capability node. Refusing unknown ids keeps the
    policy map bounded by the fleet instead of by whatever a client sends, and
    stops a stale entry from silently governing a future node that reuses an id.
    """
    devices = auth.devices
    if devices is None or not devices.is_active_kind(node_id, CAPABILITY_NODE_KIND):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown capability node")

    current = config.nodes.policy_for(node_id)
    merged = current.model_copy(update=body.model_dump(exclude_none=True))
    # Re-validate: model_copy trusts its input, so a bad literal would otherwise
    # reach the stored configuration and fail later at load time.
    try:
        policy = NodePolicyConfig.model_validate(merged.model_dump())
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    config.nodes.policies[node_id] = policy
    persist_config(request)

    # Tell the node now rather than at its next connect. Best effort: the
    # backend enforces the policy on its own side regardless.
    hub = getattr(request.app.state, "capability_hub", None)
    if hub is not None:
        if (
            current.tools_enabled != policy.tools_enabled
            or current.shell_enabled != policy.shell_enabled
        ):
            await hub.disconnect_node(node_id)
        else:
            await hub.send_policy(node_id)

    logger.info("Updated capability-node policy for %s", node_id)
    return {"status": "ok", "policy": _policy_json(policy)}
