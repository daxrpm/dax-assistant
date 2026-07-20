"""Command-line interface for the capability-node daemon."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from .credentials import (
    NodeCredentials,
    default_credentials_path,
    load_credentials,
    normalize_server_url,
    save_credentials,
)
from .daemon import EdgeDaemon

if TYPE_CHECKING:
    import argparse


def add_edge_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    edge = subparsers.add_parser("edge", help="manage an outbound capability node")
    commands = edge.add_subparsers(dest="edge_command", required=True)
    enroll = commands.add_parser("enroll", help="enroll this machine as a capability node")
    enroll.add_argument("--server", required=True)
    enroll.add_argument("--code", required=True)
    enroll.add_argument("--name", required=True)
    enroll.add_argument("--state-file", type=Path, default=default_credentials_path())
    run = commands.add_parser("run", help="run the outbound capability-node daemon")
    run.add_argument("--state-file", type=Path, default=default_credentials_path())
    status = commands.add_parser("status", help="show local capability-node enrollment")
    status.add_argument("--state-file", type=Path, default=default_credentials_path())


async def _enroll(args: argparse.Namespace) -> int:
    endpoint = normalize_server_url(args.server)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{endpoint}/api/auth/devices/enroll",
            json={
                "code": args.code,
                "name": args.name,
                "platform": sys.platform,
                "kind": "capability_node",
            },
        )
        response.raise_for_status()
        payload = response.json()
    device_id = payload.get("device_id")
    device_secret = payload.get("device_secret")
    if payload.get("ok") is not True or not isinstance(device_id, str) or not isinstance(
        device_secret, str
    ):
        raise RuntimeError("Capability-node enrollment was rejected")
    path = save_credentials(
        NodeCredentials(endpoint, device_id, device_secret, args.name), args.state_file
    )
    print(f"Capability node enrolled; credentials stored at {path}")
    return 0


async def _run(args: argparse.Namespace) -> int:
    credentials = load_credentials(args.state_file)
    daemon = EdgeDaemon(credentials)
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, daemon.stop)
    await daemon.run()
    return 0


def edge_main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.edge_command == "enroll":
        return asyncio.run(_enroll(args))
    if args.edge_command == "run":
        return asyncio.run(_run(args))
    if args.edge_command == "status":
        try:
            credentials = load_credentials(args.state_file)
        except FileNotFoundError:
            print("Capability node is not enrolled")
            return 1
        print(f"Capability node: {credentials.node_name}")
        print(f"Server: {credentials.endpoint}")
        print(f"Device ID: {credentials.device_id}")
        print(f"Credentials: {args.state_file}")
        return 0
    raise RuntimeError(f"Unknown edge command: {args.edge_command}")
