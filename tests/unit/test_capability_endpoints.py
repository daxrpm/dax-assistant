"""Endpoint validation: a node proposes an address, the backend decides.

An address the backend repeats to a phone is an instruction about where to send
a credential. A node that could name any address it liked would be able to
redirect clients somewhere the user never enrolled, so these are refusals of
attacks rather than tidiness.
"""

from __future__ import annotations

import pytest

from dax.capabilities.protocol import MAX_ENDPOINTS, HelloFrame, trusted_endpoints


def _hello(endpoints: list[str]) -> HelloFrame:
    return HelloFrame(type="hello", version=1, node_name="laptop", tools=[], endpoints=endpoints)


class TestAccepted:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "192.168.1.30:8765",
            "10.0.0.5:443",
            "172.16.4.2:1",
            "127.0.0.1:8765",
            "[fd00::1]:8765",
        ],
    )
    def test_private_addresses_pass(self, endpoint: str) -> None:
        assert trusted_endpoints(_hello([endpoint])) == [endpoint]

    def test_order_is_preserved_and_duplicates_collapse(self) -> None:
        hello = _hello(["192.168.1.30:8765", "10.0.0.5:8765", "192.168.1.30:8765"])

        assert trusted_endpoints(hello) == ["192.168.1.30:8765", "10.0.0.5:8765"]

    def test_no_endpoints_is_not_an_error(self) -> None:
        """A node with nothing listening advertises nothing."""
        assert trusted_endpoints(_hello([])) == []


class TestRefused:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "8.8.8.8:8765",
            "1.1.1.1:443",
            "93.184.216.34:8765",
        ],
    )
    def test_public_addresses_are_dropped(self, endpoint: str) -> None:
        """A routable address is not somewhere to send a phone's credential."""
        assert trusted_endpoints(_hello([endpoint])) == []

    def test_documentation_ranges_pass_and_that_is_fine(self) -> None:
        """`ipaddress` counts TEST-NET as private, and it is right to.

        203.0.113.0/24 is reserved for documentation and is not routable on the
        public internet, so admitting it fails safe — there is no host out there
        for a phone to be redirected to.
        """
        assert trusted_endpoints(_hello(["203.0.113.7:8765"])) == ["203.0.113.7:8765"]

    @pytest.mark.parametrize(
        "endpoint",
        [
            "dax.example.com:8765",
            "laptop.local:8765",
            "192.168.1.30",
            "192.168.1.30:",
            ":8765",
            "192.168.1.30:0",
            "192.168.1.30:65536",
            "192.168.1.30:-1",
            "192.168.1.30:notaport",
            "not an address",
            "",
        ],
    )
    def test_malformed_or_named_hosts_are_dropped(self, endpoint: str) -> None:
        """Names resolve to whatever the network says today; only literals pass."""
        assert trusted_endpoints(_hello([endpoint])) == []

    def test_one_bad_address_does_not_cost_the_good_ones(self) -> None:
        hello = _hello(["8.8.8.8:8765", "192.168.1.30:8765", "garbage"])

        assert trusted_endpoints(hello) == ["192.168.1.30:8765"]

    def test_an_overlong_endpoint_is_dropped(self) -> None:
        assert trusted_endpoints(_hello(["1" * 100 + ":8765"])) == []

    def test_the_list_length_is_bounded_by_the_frame_model(self) -> None:
        """The cap is enforced at parse time, before any of this runs."""
        with pytest.raises(ValueError):
            _hello([f"192.168.1.{n}:8765" for n in range(MAX_ENDPOINTS + 1)])
