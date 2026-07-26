"""Capability-node policy: who may read it, who may change it, what it means."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from dax.capabilities.tickets import verify_ticket
from dax.core.config import DaxConfig, NodePolicyConfig, NodesConfig
from dax.orchestrator.bus import MessageBus
from dax.storage.database import Database
from dax.storage.devices import CAPABILITY_NODE_KIND, CLIENT_KIND, DeviceRegistry
from dax.storage.secrets import SecretStore
from dax.web.server import create_app

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import FastAPI


class TestNodesConfigModel:
    """The policy rules, independent of transport."""

    def test_defaults_let_a_node_host_and_keep_inference_automatic(self) -> None:
        policy = NodePolicyConfig()
        assert policy.process_locally is True
        assert policy.inference == "auto"
        assert policy.voice == "auto"

    def test_unknown_node_falls_back_to_the_default_policy(self) -> None:
        assert NodesConfig().policy_for("never-enrolled") == NodePolicyConfig()

    def test_disabling_the_fleet_overrides_a_permissive_node_policy(self) -> None:
        nodes = NodesConfig(
            enabled=False,
            policies={"n1": NodePolicyConfig(process_locally=True)},
        )
        assert nodes.hosts_sessions("n1") is False
        assert nodes.lends_tool("n1", "fs_read") is False

    def test_shell_requires_an_explicit_per_node_opt_in(self) -> None:
        nodes = NodesConfig()
        assert nodes.lends_tool("n1", "fs_read") is True
        assert nodes.lends_tool("n1", "shell_run") is False
        nodes.policies["n1"] = NodePolicyConfig(shell_enabled=True)
        assert nodes.lends_tool("n1", "shell_run") is True

    def test_a_node_may_be_demoted_without_touching_its_siblings(self) -> None:
        nodes = NodesConfig(policies={"n1": NodePolicyConfig(process_locally=False)})
        assert nodes.enabled is True
        assert nodes.hosts_sessions("n1") is False
        assert nodes.hosts_sessions("n2") is True

    def test_an_invalid_inference_mode_is_refused(self) -> None:
        with pytest.raises(ValueError):
            NodePolicyConfig(inference="whatever")


@pytest.fixture
def bus() -> MessageBus:
    b = MessageBus()
    b.start()
    return b


@pytest.fixture
async def app(bus: MessageBus, tmp_path: Path):
    """Auth off so the session-gated routes are reachable without a login
    round-trip; the gating itself is asserted in ``TestNodesAuthGating``."""
    config = DaxConfig(
        security={"auth_enabled": False, "session_secret": "test-secret"},
        storage={"database_path": str(tmp_path / "dax.db")},
    )
    fastapi_app = create_app(config=config, bus=bus)
    fastapi_app.state.config = config
    fastapi_app.state.bus = bus
    fastapi_app.state.voice_listening = config.voice.enabled
    fastapi_app.state.secret_store = SecretStore(str(tmp_path / "dax.db"))

    database = Database(str(tmp_path / "dax.db"))
    await database.start()
    registry = DeviceRegistry(database)
    await registry.load()
    fastapi_app.state.auth.attach_devices(registry)
    fastapi_app.state.devices = registry
    yield fastapi_app
    await database.stop()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


async def _enroll_node(client: AsyncClient, name: str = "Laptop") -> str:
    pair = await client.post("/api/auth/devices/pair", json={"kind": CAPABILITY_NODE_KIND})
    assert pair.status_code == 200
    enroll = await client.post(
        "/api/auth/devices/enroll",
        json={"code": pair.json()["code"], "name": name, "platform": "linux"},
    )
    assert enroll.status_code == 200
    return str(enroll.json()["device_id"])


async def _enroll_client(client: AsyncClient, name: str = "Phone") -> str:
    pair = await client.post("/api/auth/devices/pair", json={"kind": CLIENT_KIND})
    enroll = await client.post(
        "/api/auth/devices/enroll",
        json={"code": pair.json()["code"], "name": name, "platform": "android"},
    )
    return str(enroll.json()["device_id"])


class TestNodeListing:
    async def test_listing_reports_policy_and_live_presence(self, client: AsyncClient) -> None:
        node_id = await _enroll_node(client)

        response = await client.get("/api/nodes")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["prefer_when_available"] is True
        row = next(n for n in body["nodes"] if n["id"] == node_id)
        assert row["name"] == "Laptop"
        # Enrolled but with no socket open. Presence is the hub's view, not the
        # fact that a row exists.
        assert row["connected"] is False
        assert row["policy"] == {
            "tools_enabled": True,
            "shell_enabled": False,
            "process_locally": True,
            "inference": "auto",
            "voice": "auto",
            "app_open_allow": [],
        }

    async def test_listing_excludes_plain_clients(self, client: AsyncClient) -> None:
        await _enroll_client(client)

        response = await client.get("/api/nodes")

        assert response.json()["nodes"] == []


class TestNodePolicyUpdates:
    async def test_update_persists_and_is_returned(self, client: AsyncClient) -> None:
        node_id = await _enroll_node(client)

        response = await client.patch(
            f"/api/nodes/{node_id}",
            json={"process_locally": False, "voice": "server", "shell_enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["policy"] == {
            "tools_enabled": True,
            "shell_enabled": True,
            "process_locally": False,
            "inference": "auto",
            "voice": "server",
            "app_open_allow": [],
        }
        listed = await client.get("/api/nodes")
        row = next(n for n in listed.json()["nodes"] if n["id"] == node_id)
        assert row["policy"]["process_locally"] is False
        assert row["policy"]["voice"] == "server"

    async def test_partial_update_leaves_the_other_fields_alone(
        self, client: AsyncClient
    ) -> None:
        node_id = await _enroll_node(client)
        await client.patch(f"/api/nodes/{node_id}", json={"inference": "local"})

        response = await client.patch(f"/api/nodes/{node_id}", json={"voice": "local"})

        assert response.json()["policy"]["inference"] == "local"
        assert response.json()["policy"]["voice"] == "local"

    async def test_unknown_node_is_refused(self, client: AsyncClient) -> None:
        response = await client.patch("/api/nodes/not-a-node", json={"process_locally": False})

        assert response.status_code == 404

    async def test_a_plain_client_may_not_be_given_a_node_policy(
        self, client: AsyncClient
    ) -> None:
        """Otherwise the map grows on ids that will never host anything."""
        device_id = await _enroll_client(client)

        response = await client.patch(
            f"/api/nodes/{device_id}", json={"process_locally": False}
        )

        assert response.status_code == 404

    async def test_a_revoked_node_may_not_be_repolicied(self, client: AsyncClient) -> None:
        node_id = await _enroll_node(client)
        await client.post(f"/api/auth/devices/{node_id}/revoke")

        response = await client.patch(f"/api/nodes/{node_id}", json={"process_locally": True})

        assert response.status_code == 404

    async def test_an_invalid_mode_is_refused_at_the_edge(self, client: AsyncClient) -> None:
        node_id = await _enroll_node(client)

        response = await client.patch(f"/api/nodes/{node_id}", json={"inference": "sideways"})

        assert response.status_code == 422

    async def test_unknown_policy_fields_are_refused(self, client: AsyncClient) -> None:
        node_id = await _enroll_node(client)

        response = await client.patch(f"/api/nodes/{node_id}", json={"root": True})

        assert response.status_code == 422


class TestFleetSwitches:
    async def test_fleet_switches_save_through_the_config_route(
        self, client: AsyncClient
    ) -> None:
        response = await client.patch(
            "/api/config/nodes", json={"prefer_when_available": False}
        )

        assert response.status_code == 200
        config = await client.get("/api/config")
        assert config.json()["nodes"]["prefer_when_available"] is False
        assert config.json()["nodes"]["enabled"] is True

    async def test_disabled_fleet_is_visible_in_the_listing(
        self, client: AsyncClient
    ) -> None:
        await _enroll_node(client)
        await client.patch("/api/config/nodes", json={"enabled": False})

        response = await client.get("/api/nodes")

        assert response.json()["enabled"] is False


class TestSessionTickets:
    """Every refusal here is one the node could not make on its own.

    A node can check a signature. It cannot know that the fleet was switched
    off, that this laptop is not meant to host, or that the phone asking was
    revoked ten seconds ago.
    """

    async def _device_headers(self, client: AsyncClient) -> dict[str, str]:
        """Enrol a phone and exchange its secret for a bearer token."""
        pair = await client.post("/api/auth/devices/pair", json={"kind": CLIENT_KIND})
        enrolled = (
            await client.post(
                "/api/auth/devices/enroll",
                json={"code": pair.json()["code"], "name": "Phone", "platform": "android"},
            )
        ).json()
        token = await client.post(
            "/api/auth/devices/token",
            json={
                "device_id": enrolled["device_id"],
                "device_secret": enrolled["device_secret"],
            },
        )
        return {"Authorization": f"Bearer {token.json()['token']}"}

    async def test_a_ticket_verifies_against_the_published_key(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        node_id = await _enroll_node(client)
        headers = await self._device_headers(client)
        app.state.capability_hub = _PresentHub({node_id: ["192.168.1.30:8765"]})

        response = await client.post(f"/api/nodes/{node_id}/session-ticket", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["endpoints"] == ["192.168.1.30:8765"]
        claims = verify_ticket(body["ticket"], body["public_key"], node_id=node_id)
        assert claims is not None
        assert claims.node_id == node_id

    async def test_the_ticket_is_bound_to_the_node_that_was_asked_for(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        node_id = await _enroll_node(client)
        headers = await self._device_headers(client)
        app.state.capability_hub = _PresentHub({node_id: []})

        body = (
            await client.post(f"/api/nodes/{node_id}/session-ticket", headers=headers)
        ).json()

        assert verify_ticket(body["ticket"], body["public_key"], node_id="other") is None

    async def test_a_session_credential_may_not_take_a_ticket(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        """The desktop runs on the laptop; it has no reason to vouch for itself."""
        node_id = await _enroll_node(client)
        app.state.capability_hub = _PresentHub({node_id: []})

        response = await client.post(f"/api/nodes/{node_id}/session-ticket")

        assert response.status_code == 403

    async def test_a_disconnected_node_yields_no_ticket(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        node_id = await _enroll_node(client)
        headers = await self._device_headers(client)
        app.state.capability_hub = _PresentHub({})

        response = await client.post(f"/api/nodes/{node_id}/session-ticket", headers=headers)

        assert response.status_code == 409

    async def test_a_node_told_not_to_host_yields_no_ticket(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        node_id = await _enroll_node(client)
        headers = await self._device_headers(client)
        app.state.capability_hub = _PresentHub({node_id: []})
        await client.patch(f"/api/nodes/{node_id}", json={"process_locally": False})

        response = await client.post(f"/api/nodes/{node_id}/session-ticket", headers=headers)

        assert response.status_code == 409

    async def test_a_disabled_fleet_yields_no_ticket(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        node_id = await _enroll_node(client)
        headers = await self._device_headers(client)
        app.state.capability_hub = _PresentHub({node_id: []})
        await client.patch("/api/config/nodes", json={"enabled": False})

        response = await client.post(f"/api/nodes/{node_id}/session-ticket", headers=headers)

        assert response.status_code == 409

    async def test_an_unknown_node_yields_no_ticket(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        headers = await self._device_headers(client)
        app.state.capability_hub = _PresentHub({})

        response = await client.post("/api/nodes/not-a-node/session-ticket", headers=headers)

        assert response.status_code == 404

    async def test_the_signing_key_survives_across_requests(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        """A key regenerated per request would invalidate live tickets."""
        node_id = await _enroll_node(client)
        headers = await self._device_headers(client)
        app.state.capability_hub = _PresentHub({node_id: []})

        first = await client.post(f"/api/nodes/{node_id}/session-ticket", headers=headers)
        second = await client.post(f"/api/nodes/{node_id}/session-ticket", headers=headers)

        assert first.json()["public_key"] == second.json()["public_key"]
        assert first.json()["ticket"] != second.json()["ticket"]


class _PresentHub:
    """Stands in for a hub with the given nodes connected."""

    def __init__(self, endpoints: dict[str, list[str]]) -> None:
        self._endpoints = endpoints

    def is_present(self, node_id: str) -> bool:
        return node_id in self._endpoints

    def endpoints_for(self, node_id: str) -> list[str]:
        return list(self._endpoints.get(node_id, []))

    async def send_policy(self, node_id: str) -> None:
        return None


class TestNodesAuthGating:
    """Node management is session-only, like device management."""

    @pytest.fixture
    async def secured(self, bus: MessageBus, tmp_path: Path):
        from dax.web.auth import hash_password

        config = DaxConfig(
            security={
                "auth_enabled": True,
                "password_hash": hash_password("correct-horse"),
                "session_secret": "test-secret",
            },
            storage={"database_path": str(tmp_path / "dax.db")},
        )
        fastapi_app = create_app(config=config, bus=bus)
        fastapi_app.state.config = config
        fastapi_app.state.bus = bus
        fastapi_app.state.voice_listening = config.voice.enabled
        database = Database(str(tmp_path / "dax.db"))
        await database.start()
        registry = DeviceRegistry(database)
        await registry.load()
        fastapi_app.state.auth.attach_devices(registry)
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        await database.stop()

    async def test_listing_requires_a_session(self, secured: AsyncClient) -> None:
        assert (await secured.get("/api/nodes")).status_code == 401

    async def test_policy_update_requires_a_session(self, secured: AsyncClient) -> None:
        response = await secured.patch("/api/nodes/anything", json={"process_locally": False})

        assert response.status_code == 401

    async def test_fleet_switches_require_a_session(self, secured: AsyncClient) -> None:
        response = await secured.patch("/api/config/nodes", json={"enabled": False})

        assert response.status_code == 401
