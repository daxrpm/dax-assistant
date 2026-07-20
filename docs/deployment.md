# Authoritative Deployment Runbook

## Topology

Run exactly one always-on authoritative backend for a Dax installation. It owns
the SQLite database, encrypted configuration and secrets, conversation history,
LLM routing, MCP registry, policy, approvals, audit data, and voice pipeline.
The browser, desktop app, and Android app are clients. A laptop may additionally
run the outbound `dax edge` capability node described in
[`capability-nodes.md`](capability-nodes.md); losing that laptop removes only its
ephemeral tools.

Desktop `local` strategy means intentionally choosing the laptop's loopback
`dax-assistant.service` as this sole authority. `remote` means choosing one
HTTPS server. Neither mode is a fallback for the other. Do not point two backend
processes at one SQLite database, copy a live database between active servers,
or attempt active-active SQLite. Dax takes a process lock and is designed for a
single writer authority.

## Supported Service Deployment

The supported production model is the `systemd --user` service installed by the
verified release installer. It uses versioned releases under
`~/.local/share/dax-assistant/releases/`, the `current` symlink, state under
`~/.local/state/dax-assistant/`, and models under
`~/.local/share/dax-assistant/models/`.

```bash
systemctl --user status dax-assistant.service
journalctl --user -u dax-assistant.service -f
curl --fail http://127.0.0.1:8420/api/health
```

`/api/health` is public probing metadata, not authentication. A usable response
has `status: "ok"`, `role: "authoritative"`, `api_protocol: "dax"`, compatible
`api_version`, `liveness: true`, `readiness: true`, and a non-empty
`instance_id`. `liveness` says the HTTP process is responding; `readiness` says
startup completed and the authority can serve clients. During startup the same
endpoint reports `status: "starting"` and `readiness: false`.

For remote access, keep FastAPI on loopback and terminate TLS at a reverse proxy
or private overlay. Proxy HTTP and WebSocket upgrades for `/ws/chat`, `/ws/logs`,
`/ws/voice`, and `/ws/capabilities`; preserve normal forwarding headers and use
timeouts suitable for long-lived sockets. First-party clients require HTTPS/WSS
for every non-loopback origin. Never expose plain port 8420 directly to the
internet. Restrict initial owner setup to a trusted network.

## Backup And Restore

Back up a consistent SQLite snapshot, not a file copied while writes are in
flight. The verified installer creates timestamped SQLite backups before an
upgrade. For an explicit backup, stop the service or use SQLite's online backup
API, then preserve these as one recovery set:

- `dax.db`, including conversations, device enrollment, encrypted config, and
  secrets;
- the matching `dax.key` when file-based key management is used;
- the exact external `DAX_MASTER_KEY` when external key management is used;
- relevant user-systemd overrides/environment files and any state outside the
  database, such as memory files and custom voice/models where required.

Never restore a database with a different key. Losing the matching key makes
encrypted material unrecoverable. Store backups and external keys separately,
encrypt backups, and test restoration.

Disaster recovery procedure:

1. Stop `dax-assistant.service` and ensure no other Dax backend uses the target
   database.
2. Preserve the failed state for investigation.
3. Restore the matching database/key recovery set with owner-only permissions.
   If using `DAX_MASTER_KEY`, restore it through the service environment instead
   of creating `dax.key`.
4. Restore required memory/state files and install a compatible backend release.
5. Start the service and wait for authoritative readiness from `/api/health`.
6. Verify login, configuration, conversations, and a non-destructive tool call.
7. Re-enroll Android/client devices and capability nodes when the restored
   device registry or server identity no longer matches the intended authority.

## Upgrades And Rollback

Install an immutable tagged release through the attested installer. It backs up
state, installs a new versioned runtime, switches `current`, restarts the service,
and waits for authoritative readiness. Failure restores the previous symlink and
service. Stop and disable an installed capability-node service before changing a
shared local runtime; the installer refuses to switch beneath an active node.

For manual rollback, stop the service, repoint `current` to a known compatible
release, restore a matching pre-upgrade database/key set if the schema cannot run
on the older release, reload user systemd, and start. Confirm health identity and
readiness before reconnecting clients. Do not downgrade a migrated database on
hope alone.

## Diagnostics And Replacement

```bash
systemctl --user status dax-assistant.service
journalctl --user -u dax-assistant.service --since today
systemctl --user status dax-assistant-node.service
journalctl --user -u dax-assistant-node.service --since today
dax edge status
```

Also check reverse-proxy logs, certificate validity, WebSocket upgrade handling,
free disk space, database/key permissions, and the complete `/api/health`
identity. Do not publish tokens, `edge.json`, pairing codes, environment files,
or decrypted configuration in diagnostics.

Desktop credentials are bound to both normalized origin and authoritative
`instance_id`. If an origin starts serving a different instance, desktop does
not send the old token; the user must authenticate to the replacement. For a
planned server replacement, stop the old authority, restore or initialize the
new sole authority, verify its identity/readiness, authenticate clients again as
needed, and issue fresh enrollment codes for capability nodes. Never run the old
and replacement authorities as an active-active pair.
