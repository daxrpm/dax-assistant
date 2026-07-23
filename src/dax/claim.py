"""First-run account creation from the machine running the backend.

`/api/auth/setup` only accepts loopback callers, so an unclaimed backend cannot
be taken over by whoever reaches it first on the network. That is the right
default, but it leaves a headless server with no way to set its own password —
which is what this command is for. It runs *on* the server, so it is loopback.

It deliberately talks to the running backend over HTTP rather than opening the
secret store directly: the store takes an exclusive process lock, so writing to
it would mean stopping the service first.
"""

from __future__ import annotations

import getpass
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import argparse

DEFAULT_URL = "http://127.0.0.1:8420"
MIN_PASSWORD_LENGTH = 8


def add_claim_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "claim",
        help="Create the first account on a backend running on this machine",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Backend base URL, which must be loopback (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from stdin instead of prompting, for scripted installs",
    )


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    while True:
        password = getpass.getpass("Choose a password for Dax: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(
                f"Too short — use at least {MIN_PASSWORD_LENGTH} characters.",
                file=sys.stderr,
            )
            continue
        if password != getpass.getpass("Repeat it: "):
            print("Those did not match. Try again.", file=sys.stderr)
            continue
        return password


def claim_main(args: argparse.Namespace) -> int:
    import httpx

    url = str(args.url).rstrip("/")
    password = _read_password(bool(args.password_stdin))
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"The password must be at least {MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        return 2

    try:
        response = httpx.post(
            f"{url}/api/auth/setup", json={"password": password}, timeout=30.0
        )
    except httpx.HTTPError as exc:
        print(f"Cannot reach the backend at {url}: {exc}", file=sys.stderr)
        print(
            "Start it with `systemctl --user start dax-assistant` and try again.",
            file=sys.stderr,
        )
        return 1

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 200 and body.get("ok"):
        print("Account created. Sign in with this password from any Dax client.")
        return 0

    detail = body.get("detail") or f"the backend answered {response.status_code}"
    print(f"Could not create the account: {detail}", file=sys.stderr)
    return 1
