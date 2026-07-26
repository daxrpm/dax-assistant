"""Wake-word arbitration: one room, several microphones, one answer."""

from __future__ import annotations

import threading

import pytest

from dax.voice.arbiter import HOST_SOURCE_ID, WakeArbiter


class TestSingleClaimant:
    def test_a_lone_microphone_wins_without_waiting_for_rivals(self) -> None:
        arbiter = WakeArbiter(window_s=0.02)
        claim = arbiter.claim(HOST_SOURCE_ID, 0.9)
        assert arbiter.wait_for(claim) is True

    def test_the_winner_holds_the_wake_path_until_it_releases(self) -> None:
        arbiter = WakeArbiter(window_s=0.02)
        arbiter.wait_for(arbiter.claim(HOST_SOURCE_ID, 0.9))
        assert arbiter.held_by == HOST_SOURCE_ID

        # The tail of the same sentence must not open a second turn.
        assert arbiter.wait_for(arbiter.claim("laptop", 0.99)) is False

        arbiter.release(HOST_SOURCE_ID)
        assert arbiter.held_by is None
        assert arbiter.wait_for(arbiter.claim("laptop", 0.7)) is True

    def test_release_by_the_wrong_source_is_ignored(self) -> None:
        arbiter = WakeArbiter(window_s=0.02)
        arbiter.wait_for(arbiter.claim(HOST_SOURCE_ID, 0.9))
        arbiter.release("laptop")
        assert arbiter.held_by == HOST_SOURCE_ID


class TestCompetingClaimants:
    def test_the_loudest_microphone_answers_and_the_other_stands_down(self) -> None:
        arbiter = WakeArbiter(window_s=0.15)
        results: dict[str, bool] = {}

        def claim(source: str, score: float) -> None:
            results[source] = arbiter.wait_for(arbiter.claim(source, score))

        threads = [
            threading.Thread(target=claim, args=("laptop", 0.62)),
            threading.Thread(target=claim, args=(HOST_SOURCE_ID, 0.94)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert results == {HOST_SOURCE_ID: True, "laptop": False}

    def test_a_claim_arriving_inside_the_window_is_judged_with_the_first(self) -> None:
        arbiter = WakeArbiter(window_s=0.2)
        early = arbiter.claim("laptop", 0.5)
        late = arbiter.claim("server", 0.8)

        won: dict[str, bool] = {}
        thread = threading.Thread(
            target=lambda: won.update(laptop=arbiter.wait_for(early))
        )
        thread.start()
        won["server"] = arbiter.wait_for(late)
        thread.join(timeout=5)

        assert won == {"server": True, "laptop": False}

    def test_identical_scores_still_produce_exactly_one_winner(self) -> None:
        arbiter = WakeArbiter(window_s=0.15)
        first = arbiter.claim("b-node", 0.8)
        second = arbiter.claim("a-node", 0.8)

        won: dict[str, bool] = {}
        thread = threading.Thread(
            target=lambda: won.update({"b-node": arbiter.wait_for(first)})
        )
        thread.start()
        won["a-node"] = arbiter.wait_for(second)
        thread.join(timeout=5)

        assert sum(won.values()) == 1


class TestStuckHolds:
    def test_a_node_that_never_releases_stops_wedging_the_wake_path(self) -> None:
        now = [1000.0]
        arbiter = WakeArbiter(
            window_s=0.0, hold_timeout_s=30.0, clock=lambda: now[0]
        )
        assert arbiter.wait_for(arbiter.claim("laptop", 0.9)) is True
        assert arbiter.held_by == "laptop"

        # The laptop dropped off mid-turn and never sent its release.
        now[0] += 31.0
        assert arbiter.held_by is None
        assert arbiter.wait_for(arbiter.claim(HOST_SOURCE_ID, 0.5)) is True

    def test_reset_frees_everyone_waiting(self) -> None:
        arbiter = WakeArbiter(window_s=5.0)
        claim = arbiter.claim("laptop", 0.9)
        threading.Timer(0.05, arbiter.reset).start()
        assert arbiter.wait_for(claim) is False
        assert arbiter.held_by is None


@pytest.mark.parametrize("score", [0.0, 1.0])
def test_extreme_scores_are_accepted(score: float) -> None:
    arbiter = WakeArbiter(window_s=0.02)
    assert arbiter.wait_for(arbiter.claim("laptop", score)) is True
