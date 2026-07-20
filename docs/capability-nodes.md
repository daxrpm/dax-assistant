# Capability Nodes

A capability node lets the authoritative Dax backend use selected tools on a
laptop without moving the backend to that laptop. The backend remains the only
owner of SQLite, encrypted configuration, conversations, LLM routing, policy,
approvals, and audit records. The node is an outbound, authenticated executor.
If the laptop sleeps, shuts down, or loses its network, its tools disappear;
server chat and all other backend functions continue.

The current implementation supports one live connection per enrolled node and
the trusted inventory bundled with `dax-system`. It does not discover arbitrary
MCP servers on the laptop, synchronize files, queue calls while offline, or
move authority between hosts. A reconnect for the same node replaces the older
socket and inventory generation.

Direct client-to-node sessions are **partially built**. The trust layer exists
and is described under [Session trust](#session-trust); the listening socket
does not. A node therefore still lends tools through the backend. Local TTS is
the exception: the backend may route an authenticated mobile synthesis request
over the capability socket and returns the validated WAV to the phone. The
phone never connects directly to the node for that flow.

## Node Policy

What a node is asked to do is configuration, so the backend owns it, keyed by
device id. A node reads its own entry when it connects rather than keeping a
copy — that is what makes "stop processing on the laptop" take effect from
whichever client is in reach.

| Setting | Values | Meaning |
| --- | --- | --- |
| `tools_enabled` | on/off | Whether the node lends its typed PC tools. |
| `shell_enabled` | on/off | Whether `shell_run` is advertised; off by default. |
| `process_locally` | on/off | May host a client session and run the turn. Off leaves it lending tools only. |
| `inference` | `auto`/`local`/`server` | Where the model runs. |
| `voice` | `auto`/`local`/`server` | Where mobile TTS synthesis runs; direct node STT is not implemented yet. |

Two fleet-wide switches sit above these: `enabled` refuses every node outright,
and `prefer_when_available` decides whether clients reach for a node at all.
Either one being off overrides a permissive per-node policy.

Edit per-node policy in the desktop or web UI under **Settings → Capabilities →
Capability nodes**. The Android app gets only the two fleet switches and live
presence, under **Settings → Local node** — an enrolled device may not enumerate
its siblings, and a per-node editor would require exactly that enumeration.

Keep `inference` on `auto`. It pins the model to the node only when the model is
itself local (Ollama on the node's GPU). A cloud provider is dominated by the
round trip to the provider, so routing that HTTPS call through a laptop adds a
hop and removes none. `voice` is the setting that actually pays: audio is bulky,
and keeping speech next to the microphone avoids crossing the network twice.

`CapabilityHub.send_policy` pushes changes to a connected node immediately. That
push is best effort and is not a security control — the backend enforces the
policy on its own side regardless of whether the node obeyed.

## Session Trust

A phone that finds a laptop on the WiFi has learned nothing about who that
laptop is. Discovery is a hint; it is never evidence. So the backend vouches:
the phone asks it for a ticket naming a specific node, and the node verifies
that ticket before serving anyone.

Tickets are Ed25519, not HMAC. The existing session and device tokens are signed
with a shared secret, and a node holding that secret could mint device tokens
and session cookies for the backend itself. With a signature scheme the node
verifies but cannot produce, a compromised laptop can impersonate nobody. There
is deliberately no algorithm field in the payload — negotiable algorithms are
where JWT implementations get broken.

A ticket names one node and one device and lives for two minutes, so a hostile
node cannot collect tickets and replay them against the real one. The backend
signing key is generated on first use and kept in the encrypted secret store;
the node receives only the public half, in its `ready` frame.

`POST /api/nodes/{id}/session-ticket` is device-authenticated and refuses what
the node could not check for itself: a switched-off fleet, a node not configured
to host, a disconnected node, an unknown node, and a session credential rather
than a device one. A revoked phone stops receiving tickets immediately, because
revocation is enforced at token validation rather than at issue.

Node addresses follow the same rule as node tool schemas: proposed, not trusted.
A node may advertise where it can be reached, and the backend keeps only
private, link-local, and loopback literals. An address the backend repeats to a
phone is an instruction about where to send a credential, so a node must not be
able to name a routable one.

## Enroll A Laptop

1. Install only the node runtime and unit. This never installs or starts an
   authoritative backend and leaves the node disabled:

   ```bash
   bash install.sh --version "$VERSION" --node-only
   ```

2. In native Dax Desktop, run post-login setup. Desktop asks the authenticated
   backend for a one-use capability code, redeems it natively, and writes the
   credential with owner-only permissions. It never invokes a general shell.
   Browser-only and headless clients retain the manual fallback:

   ```bash
   dax edge enroll --server https://dax.example --code CODE --name NAME
   ```

3. Explicitly consent in Desktop to enable/start the service, or do it manually:

   ```bash
   systemctl --user enable --now dax-assistant-node.service
   systemctl --user status dax-assistant-node.service
   journalctl --user -u dax-assistant-node.service -f
   ```

`scripts/install.sh --node-only` installs a separate `node-current` runtime and
the node unit but intentionally does not enable or start it. It cannot move or
start `dax-assistant.service`. Enrollment must happen first. The managed service
uses `~/.local/state/dax-assistant/edge.json`; its directory is mode `0700` and
the file is atomically written mode `0600`. `--state-file PATH` remains available
for manually managed `enroll`, `run`, and `status` processes.

Remote server URLs must be HTTPS and the derived `/ws/capabilities` connection
uses WSS. Plain HTTP/WS is accepted only for loopback. URLs containing
credentials, a path, query, or fragment are rejected. The node initiates every
connection; no inbound laptop port is required.

## Tools And Safety

The server accepts only the bundled, server-owned inventory and schemas:
`system_info`, `fs_list`, `fs_read`, `fs_search`, `clipboard_get`, `notify`,
`fs_write`, `shell_run`, `open_path`, and `clipboard_set`. Tools are registered
ephemerally as `node_<stable-id-hash>__<tool>`, for example
`node_0123456789abcdef__fs_read`. The opaque prefix prevents collisions and is
not a friendly node name.

Node tools use the authoritative backend's normal `allow`/`ask`/`deny` policy.
`shell_run` is absent until explicitly enabled for that node. Every node shell
call then requires one-time approval in the session-owning client. Timeout, no
eligible UI, disconnect, or revocation fails closed. The node independently
applies `DAX_SYSTEM_SHELL_ALLOW` as a hard binary cap, so backend approval cannot
permit a binary the PC owner excluded.

Typed file-tool paths are resolved on the laptop and must remain under
`DAX_SYSTEM_ROOTS`, an OS-path-separator-delimited list; the default is the
laptop user's home. Generic argv paths cannot be interpreted safely for every
binary, so roots set the shell working directory but do not claim to confine
every command argument. Commands are parsed into argv, reject metacharacters,
use a system PATH, and execute directly. This is not SSH, an interactive shell,
or a pipeline.

## Local TTS

Android still calls the authoritative backend's `POST /api/voice/synthesize`.
When fleet preference and the node's `voice` policy allow it, the backend sends
a bounded synthesis request to a connected node. The node uses local Kokoro or
Piper only, returns chunked PCM16 with a byte count and SHA-256, and the backend
validates it before returning WAV audio. OpenAI keys are never sent to a node.

`voice=auto` offloads configured Kokoro/Piper and keeps OpenAI on the backend.
`voice=local` requires node-local Kokoro/Piper and fails rather than silently
using OpenAI. Missing nodes or transport failures under `auto` fall back to the
backend. Models live under `~/.local/share/dax-assistant/models`, or the path set
by `DAX_MODELS_PATH` in a service override.

## Offline, Reconnect, And Revocation

Inventory exists only while the node's authenticated WebSocket is live. An
in-flight call fails if the connection drops; calls are not replayed. The daemon
refreshes short-lived tokens by reconnecting and uses capped exponential jitter
after failures. Once connectivity returns, it advertises a fresh inventory and
becomes available without moving any server state.

The desktop and web device lists report live presence separately from last
seen. Revoking or deleting a capability node there immediately disconnects its
socket, unregisters its tools, fails pending calls, and prevents future token
refresh. The local `edge.json` is not remotely erased; delete it or re-enroll
the laptop after revocation. Server replacement creates a different authority,
so generate a new code on the replacement server and enroll again.
