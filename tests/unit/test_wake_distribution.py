"""Wake word heard on a laptop: claim, arbitration, and streamed audio."""

from __future__ import annotations

import asyncio
import base64

import numpy as np
import pytest

from dax.capabilities.hub import CapabilityHub
from dax.core.config import DaxConfig, NodePolicyConfig, NodesConfig, VoiceConfig
from dax.edge.protocol import parse_wake_policy
from dax.edge.wake import WakeListener
from dax.mcp.manager import MCPManager
from dax.storage.database import Database
from dax.storage.devices import CAPABILITY_NODE_KIND, DeviceRegistry
from dax.voice.arbiter import HOST_SOURCE_ID, WakeArbiter

from .test_capabilities import FakeWebSocket


class FakePipeline:
    """Just enough pipeline for the hub to open and close a wake turn."""

    def __init__(self, *, window_s: float = 0.02) -> None:
        self.enabled = True
        self.arbiter = WakeArbiter(window_s=window_s, suppress_s=1.5)
        self.owner: str | None = None
        self.source = None
        self.wake_requests: list[str] = []
        self.released: list[str] = []
        self.on_end = None
        self.speaker = None
        self.refuse = False
        self.state = "idle"

    def set_remote_wake_end_callback(self, callback) -> None:
        self.on_end = callback

    def set_remote_wake_speaker(self, callback) -> None:
        self.speaker = callback

    def acquire_remote_owner(self, owner: str) -> int:
        if self.refuse:
            raise RuntimeError("Voice pipeline is busy")
        self.owner = owner
        return 1

    def select_audio_source(self, source) -> None:
        self.source = source

    def request_remote_wake(self, owner: str) -> None:
        self.wake_requests.append(owner)

    def release_remote_owner(self, owner: str) -> None:
        self.released.append(owner)
        self.owner = None


def _hello() -> dict[str, object]:
    return {"type": "hello", "version": 1, "tools": []}


@pytest.fixture
async def wake_env(tmp_path):
    database = Database(str(tmp_path / "dax.db"))
    await database.start()
    devices = DeviceRegistry(database)
    await devices.load()
    node, _ = await devices.enroll(
        name="laptop", platform="linux", kind=CAPABILITY_NODE_KIND
    )
    manager = MCPManager(DaxConfig().mcp)
    nodes = NodesConfig(policies={node.id: NodePolicyConfig()})
    hub = CapabilityHub(manager, devices, nodes, voice=VoiceConfig())
    pipeline = FakePipeline()
    hub.set_pipeline(pipeline)
    socket = FakeWebSocket(_hello())
    task = asyncio.create_task(hub.handle(socket, node.id))
    await socket.wait_for_type("ready")
    yield hub, pipeline, socket, node.id
    await socket.close()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await hub.stop()
    await database.stop()


class TestPolicyPush:
    async def test_the_node_is_told_what_to_listen_for(self, wake_env) -> None:
        _, _, socket, _ = wake_env
        policy = await socket.wait_for_type("policy")
        assert policy["wake_word"] is True
        assert policy["wake_word_model"] == "hey_jarvis"
        assert policy["wake_word_threshold"] == pytest.approx(0.7)

        # The node parses exactly what the backend sent.
        parsed = parse_wake_policy(policy)
        assert parsed is not None
        assert parsed.enabled is True
        assert parsed.model == "hey_jarvis"

    async def test_a_policy_without_wake_fields_leaves_the_node_deaf(self) -> None:
        # An older backend. Listening without an arbiter on the other side would
        # let this node answer over every other microphone in the house.
        assert parse_wake_policy({"type": "policy", "process_locally": True}) is None

    async def test_a_disabled_node_is_refused_the_wake(self, wake_env) -> None:
        hub, _, socket, node_id = wake_env
        hub.nodes.policies[node_id] = NodePolicyConfig(wake_word=False)

        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.9}
        )
        verdict = await socket.wait_for_type("wake_yield")
        assert verdict["claim_id"] == "c1"


class TestGrantedTurn:
    async def test_an_uncontested_claim_opens_a_turn_on_the_node(
        self, wake_env
    ) -> None:
        _, pipeline, socket, node_id = wake_env
        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.8}
        )
        grant = await socket.wait_for_type("wake_grant")

        assert grant["claim_id"] == "c1"
        assert pipeline.owner == node_id
        assert pipeline.wake_requests == [node_id]
        assert pipeline.source is not None

    async def test_streamed_audio_reaches_the_pipeline_in_order(
        self, wake_env
    ) -> None:
        _, pipeline, socket, _ = wake_env
        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.8}
        )
        grant = await socket.wait_for_type("wake_grant")
        lease = grant["lease_id"]

        pcm = np.full(160, 700, dtype="<i2").tobytes()
        for seq in range(3):
            await socket.push(
                {
                    "type": "audio_chunk",
                    "generation": 1,
                    "lease_id": lease,
                    "seq": seq,
                    "data": base64.b64encode(pcm).decode(),
                }
            )
        await asyncio.sleep(0.05)

        received = [pipeline.source.read_chunk(timeout=0.5) for _ in range(3)]
        assert all(chunk is not None and len(chunk) == 160 for chunk in received)

    async def test_a_sequence_gap_drops_the_connection(self, wake_env) -> None:
        _, _, socket, _ = wake_env
        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.8}
        )
        grant = await socket.wait_for_type("wake_grant")

        pcm = base64.b64encode(np.zeros(80, dtype="<i2").tobytes()).decode()
        # Frame 0 never arrived: splicing over the gap would hand the
        # transcriber an utterance the user never said.
        await socket.push(
            {
                "type": "audio_chunk",
                "generation": 1,
                "lease_id": grant["lease_id"],
                "seq": 4,
                "data": pcm,
            }
        )
        await asyncio.sleep(0.05)
        assert socket.closed is True

    async def test_ending_the_turn_hands_the_microphone_back(
        self, wake_env
    ) -> None:
        _, pipeline, socket, node_id = wake_env
        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.8}
        )
        grant = await socket.wait_for_type("wake_grant")

        await socket.push(
            {
                "type": "audio_end",
                "generation": 1,
                "lease_id": grant["lease_id"],
                "reason": "complete",
            }
        )
        await asyncio.sleep(0.05)
        assert pipeline.released == [node_id]
        assert pipeline.source is None

    async def test_audio_end_during_processing_retains_the_output_route(
        self, wake_env
    ) -> None:
        hub, pipeline, socket, node_id = wake_env
        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.8}
        )
        grant = await socket.wait_for_type("wake_grant")
        pipeline.state = "processing"

        await socket.push(
            {
                "type": "audio_end",
                "generation": 1,
                "lease_id": grant["lease_id"],
                "reason": "complete",
            }
        )
        await asyncio.sleep(0.05)

        assert pipeline.released == []
        assert hub._connections[node_id].wake is not None
        pipeline.state = "idle"
        assert pipeline.on_end is not None
        pipeline.on_end(node_id)
        await asyncio.sleep(0.05)
        assert pipeline.released == [node_id]

    async def test_a_busy_pipeline_yields_instead_of_half_opening_a_turn(
        self, wake_env
    ) -> None:
        _, pipeline, socket, _ = wake_env
        pipeline.refuse = True

        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.9}
        )
        verdict = await socket.wait_for_type("wake_yield")

        assert verdict["claim_id"] == "c1"
        assert pipeline.wake_requests == []
        # The hold must not survive a turn that never opened.
        assert pipeline.arbiter.held_by is None


class TestHostCompetition:
    async def test_a_louder_host_microphone_beats_the_node(self, wake_env) -> None:
        _, pipeline, socket, _ = wake_env
        arbiter = pipeline.arbiter

        # The host heard it more clearly and claims first.
        host_claim = arbiter.claim(HOST_SOURCE_ID, 0.95)
        await socket.push(
            {"type": "wake_claim", "generation": 1, "claim_id": "c1", "score": 0.40}
        )
        assert await asyncio.to_thread(arbiter.wait_for, host_claim) is True

        verdict = await socket.wait_for_type("wake_yield")
        assert verdict["claim_id"] == "c1"
        assert verdict["suppress_ms"] == 1500
        assert pipeline.wake_requests == []


class TestNodeListener:
    """The laptop side: a detection becomes a claim, never a direct answer."""

    async def test_a_yield_suppresses_the_local_detector(self) -> None:
        sent: list[dict[str, object]] = []

        async def send(frame: dict[str, object]) -> None:
            sent.append(frame)

        listener = WakeListener(send, asyncio.get_running_loop())
        listener._claim_id = "c1"
        listener.on_yield("c1", suppress_ms=1500)

        assert listener._lease_id is None
        # Deaf for a moment, so the rest of the sentence cannot re-trigger it.
        assert listener._suppressed_until > 0

    async def test_a_grant_for_an_abandoned_claim_is_ignored(self) -> None:
        async def send(frame: dict[str, object]) -> None:
            return None

        listener = WakeListener(send, asyncio.get_running_loop())
        listener._claim_id = "current"
        listener.on_grant("stale", "lease-1")

        # Streaming on a stale grant would send audio from a sentence that has
        # already moved on.
        assert listener._lease_id is None
