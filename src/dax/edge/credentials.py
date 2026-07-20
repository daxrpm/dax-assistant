"""Secure local persistence for capability-node credentials."""

from __future__ import annotations

import ipaddress
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class NodeCredentials:
    endpoint: str
    device_id: str
    device_secret: str = field(repr=False)
    node_name: str


def default_credentials_path() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
    return base / "dax-assistant" / "edge.json"


def _is_loopback(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def normalize_server_url(value: str) -> str:
    """Return a canonical HTTP base URL, rejecting insecure remote endpoints."""
    raw = value.strip()
    if not raw:
        raise ValueError("Server URL is required")
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme in {"ws", "wss"}:
        scheme = "http" if scheme == "ws" else "https"
    if scheme not in {"http", "https"}:
        raise ValueError("Server URL must use HTTP(S) or WS(S)")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Server URL must contain a host and no credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Server URL must not contain a query or fragment")
    path = parsed.path.rstrip("/")
    if path:
        raise ValueError("Server URL must not contain a path")
    if scheme == "http" and not _is_loopback(parsed.hostname):
        raise ValueError("Remote capability nodes require HTTPS/WSS")

    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit(SplitResult(scheme, f"{host}{port}", "", "", ""))


def websocket_url(endpoint: str) -> str:
    parsed = urlsplit(normalize_server_url(endpoint))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, "/ws/capabilities", "", ""))


def save_credentials(credentials: NodeCredentials, path: Path | None = None) -> Path:
    """Atomically write credentials with owner-only permissions."""
    destination = path or default_credentials_path()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    payload = json.dumps(asdict(credentials), sort_keys=True).encode() + b"\n"

    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return destination


def load_credentials(path: Path | None = None) -> NodeCredentials:
    source = path or default_credentials_path()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid edge credential file")
    try:
        return NodeCredentials(
            endpoint=normalize_server_url(str(data["endpoint"])),
            device_id=str(data["device_id"]),
            device_secret=str(data["device_secret"]),
            node_name=str(data["node_name"]),
        )
    except KeyError as exc:
        raise ValueError(f"Edge credential file is missing {exc.args[0]}") from exc
