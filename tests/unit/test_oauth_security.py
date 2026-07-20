"""Focused security tests for MCP OAuth routes."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from dax.web.routes import oauth


def test_callback_html_escapes_provider_error() -> None:
    page = oauth._callback_html(False, '<script>alert("xss")</script>')

    assert "<script>alert" not in page
    assert "&lt;script&gt;alert" in page


async def test_expired_pending_state_is_rejected(monkeypatch) -> None:
    state = "expired-state"
    oauth._pending_flows[state] = {
        "created_at": time.time() - oauth._PENDING_FLOW_TTL_SECONDS - 1,
    }

    class UnexpectedClient:
        def __init__(self, *args, **kwargs) -> None:
            pytest.fail("expired state must not perform a token request")

    monkeypatch.setattr(oauth.httpx, "AsyncClient", UnexpectedClient)
    request = Request({"type": "http", "app": object()})
    response = await oauth.oauth_callback(request, code="code", state=state)

    assert response.status_code == 400
    assert state not in oauth._pending_flows


async def test_private_metadata_url_is_rejected_without_request() -> None:
    class UnexpectedClient:
        async def get(self, url: str):
            pytest.fail(f"unsafe URL was requested: {url}")

    result = await oauth._parse_www_authenticate(
        'Bearer resource_metadata="http://127.0.0.1/secrets"',
        UnexpectedClient(),  # type: ignore[arg-type]
        allowed_host="mcp.example.com",
    )

    assert result is None


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/token",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/token",
        "file:///etc/passwd",
        "https://user:password@example.com/token",
    ],
)
async def test_unsafe_oauth_urls_are_rejected(url: str) -> None:
    assert not await oauth._safe_outbound_url(url, allowed_host="mcp.example.com")


async def test_configured_private_host_remains_supported() -> None:
    assert await oauth._safe_outbound_url(
        "http://127.0.0.1:9000/token", allowed_host="127.0.0.1",
    )


async def test_hostname_resolving_to_private_address_is_rejected(monkeypatch) -> None:
    loop = oauth.asyncio.get_running_loop()

    async def private_dns(*args, **kwargs):
        return [(2, 1, 6, "", ("10.0.0.7", 443))]

    monkeypatch.setattr(loop, "getaddrinfo", private_dns)
    assert not await oauth._safe_outbound_url(
        "https://provider.example/token", allowed_host="provider.example",
    )


async def test_metadata_redirect_is_not_followed() -> None:
    class RedirectingClient:
        def __init__(self) -> None:
            self.urls: list[str] = []

        async def get(self, url: str):
            self.urls.append(url)
            return SimpleNamespace(status_code=302)

    client = RedirectingClient()
    result = await oauth._fetch_as_metadata(
        "https://8.8.8.8/oauth",
        client,  # type: ignore[arg-type]
    )

    assert result is None
    assert len(client.urls) == 3
