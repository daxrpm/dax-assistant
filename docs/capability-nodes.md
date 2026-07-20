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

## Enroll A Laptop

1. In an authenticated desktop or web UI, open the paired-devices area and
   choose **Add laptop capability**. This creates a short-lived, one-use code
   specifically for a `capability_node`, not a normal client credential.
2. On the laptop, use the exact command shown by the UI:

   ```bash
   dax edge enroll --server https://dax.example --code CODE --name NAME
   ```

3. Check the local enrollment with `dax edge status`.
4. Run interactively with `dax edge run`, or install and explicitly enable the
   user service:

   ```bash
   systemctl --user enable --now dax-assistant-node.service
   systemctl --user status dax-assistant-node.service
   journalctl --user -u dax-assistant-node.service -f
   ```

`scripts/install.sh --with-node` installs the node unit but intentionally does
not enable or start it. Enrollment must happen first. The default credential is
`$XDG_STATE_HOME/dax-assistant/edge.json`, or
`~/.local/state/dax-assistant/edge.json` when `XDG_STATE_HOME` is unset. Its
directory is mode `0700` and the file is atomically written mode `0600`. The
service has `ConditionPathExists` for that file. `--state-file PATH` overrides
the location for `enroll`, `run`, and `status`.

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
Canonical node `shell_run` tools receive the same shell-policy classification,
and ask-classified calls require approval in the session-owning client. Timeout,
no eligible UI, disconnect, or revocation fails closed. The backend records the
tool result in its normal audit path.

File paths are resolved on the laptop and must remain under
`DAX_SYSTEM_ROOTS`, an OS-path-separator-delimited list; the default is the
laptop user's home. The node service inherits its environment, so configure
roots in a user-systemd override and restart it. `shell_run` is also gated by
the authoritative backend's managed shell allowlist and per-call approval gate.
On the laptop it is parsed into argv, rejects shell metacharacters, and executes
directly without a shell. It is not a general shell or pipeline.

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
