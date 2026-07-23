# Desktop Architecture

This document is the implementation map for Dax Desktop. `AGENTS.md` contains the short operational rules; this file records the boundaries and invariants that future work must preserve.

## Process boundaries

Dax Desktop has three layers:

1. One always-on Python backend is authoritative for SQLite, conversations, agent orchestration, LLM routing, MCP, policy, approvals, configuration, persistence, voice routing, and the voice state machine. It may delegate bounded local TTS execution to an enrolled node without delegating authority.
2. The Tauri Rust core owns OS capabilities: windows, tray, global shortcuts, autostart, notifications, systemd control, host metrics, keyring access, and validated local preferences.
3. The React webview owns presentation and backend protocols. It calls FastAPI directly; Rust is not an HTTP proxy.

HTTP uses bearer authentication. WebSockets use the same token as an authenticated query parameter because the browser WebSocket API cannot set an Authorization header. Remote origins require HTTPS/WSS unless the host is a literal private address (RFC 1918, loopback, IPv6 ULA/link-local, or the RFC 6598 range overlays such as Tailscale assign from), the one case where cleartext provably cannot leave the local network.

An optional `dax edge` process on the laptop is a separate outbound capability
node, not a backend sidecar. It contributes laptop tools only while online. See
[`capability-nodes.md`](capability-nodes.md).

## Connection strategy

Rust persists a versioned connection document. Schema v3 contains:

- `strategy`: `local` or `remote`.
- `local_url`: a validated loopback URL.
- `remote_url`: a validated HTTPS URL when remote access is configured.
- `active_url`: the configured authority selected by resolution.
- `active_server_id`: the last validated authoritative instance identity.
- `onboarding_complete`: whether first-run setup has been accepted.

Legacy v1 `{mode,url}` and schema-v2 documents are migrated on read and rewritten
atomically. A v2 local strategy remains local. A v2 remote strategy remains
remote. A v2 `hybrid` strategy becomes remote and selects its configured
`remote_url`; it does not preserve or emulate fallback. Migration clears the old
server identity so health must establish the current authority.

Resolution rules are deterministic:

- Local probes only `local_url`; choosing it means deliberately running this
  laptop as the sole authority.
- Remote probes only `remote_url` and never tries loopback.
- Starting `dax-assistant.service` requires explicit consent and is attempted only for the local candidate.
- A failed authority remains failed until it recovers or the user explicitly
  changes strategy. There is no alternate-authority failover.

Health probing accepts only a response with `status=ok`, `role=authoritative`,
`api_protocol=dax`, compatible `api_version`, true liveness/readiness, and a
non-empty `instance_id`. Tokens are stored and authorized by normalized URL
origin plus this instance identity. Changing either shuts down realtime stores
and requires the matching credential; an old token is never sent to a different
server now occupying the same origin.

## First-run onboarding

Native desktop launches onboarding before authentication when `onboarding_complete` is false. Browser-only development skips native setup.

The flow covers:

1. Privacy and where conversations are processed.
2. Local sole-authority or remote sole-authority strategy.
3. URL validation and connectivity checks.
4. Detection and optional start of the existing systemd user service.
5. Review and atomic persistence.

The desktop package does not silently install the Python backend. Missing service state is reported honestly. The same strategy editor remains available in Desktop Settings and from the unreachable-backend screen. It can reconfigure local or remote mode, validate the selected URL, and request consent before starting `dax-assistant.service`; reconfiguration never copies a token between authorities.

After login, native Desktop can enrol the same machine as a capability node. A
main-window-only Rust command redeems a one-use code against the already
validated authority and writes the daemon credential atomically. It accepts no
URL, path, executable, or argv from React. Enabling and starting the fixed node
unit remains separate explicit consent.

## Realtime stores

Voice and logs use one demand-managed external store per webview window. Chat uses one isolated store per `session_id`. Stores survive route changes, close on logout/pagehide, keep bounded buffers, and reject frames belonging to another chat session.

`/ws/voice` carries state, user transcripts, the current `speech` sentence,
speaker verdict, errors, and level frames. In default server-output mode Kokoro
emits each sentence after synthesis and immediately before playback; in
`client_text` mode the sentence is emitted without server audio. The command
deck and HUD can therefore replace the user transcript with the active reply.
Level data always preserves `source: input|output`:

- `input` is microphone energy.
- `output` is TTS playback energy, including Kokoro.

Remote microphone input is an authenticated exclusive lease. It accepts bounded PCM16LE, 16 kHz, mono frames during push-to-talk only. In default `server` output mode the backend synthesizes and plays TTS on its host. A `client_text` lease instead emits sentence `speech` text and performs no server synthesis, playback, or earcon so the client may synthesize locally. Server-synthesized audio streaming to clients is not implemented.

## Orbita rendering

The center orb and HUD use Canvas 2D through an imperative ref. Level frames never enter React state.

The renderer uses:

- Separate bounded ring buffers for input and output.
- RMS, peak, and spectrum energy rather than a synthetic animation.
- An outer, sharper microphone wave and an inner perspective-compressed TTS wave.
- A radial-gradient sphere, perspective orbital ellipses, and z-sorted particles for pseudo-3D depth.
- Delta-time springs for transitions.
- DPR-aware resizing and reduced-motion behavior.
- Automatic requestAnimationFrame shutdown after both sources settle in idle.

This preserves the visual identity with a lightweight renderer. The indigo accent remains reserved for voice and primary actions.

## Media integration

The command deck reads MPRIS through fixed `playerctl` arguments in Rust. The
media island exposes metadata and controls, extrapolates position between polls,
and receives a compact 40-band PipeWire spectrum instead of PCM. Trusted Spotify
CDN artwork and strictly validated Chromium cache images may render as a blurred,
darkened background; arbitrary `file://` and remote artwork remain blocked.

Media ducking is opt-in per device and restores the exact original MPRIS volume.
The speaking volume is configurable from 10–100% and defaults to 40%. Listening
and processing preserve floors of 60% and 75%, avoiding aggressive attenuation
before speech while retaining clear feedback.

## Window chrome and surfaces

The main window supports two persisted modes:

- `custom` is the default 31 px Dax frame with drag region and scoped hide, minimize, and maximize/restore commands.
- `native` restores compositor decorations for users who prefer system chrome.

The HUD never inherits main-window chrome. Wayland may ignore exact HUD positioning.

The dark palette uses a blue-black ground and stepped cool surface tokens rather than one repeated panel color. Floating islands are separated by space, luminance, ambient shadow, and a top inset highlight. Visible outline grids are not part of the design language. Compact breakpoints reduce gutter while preserving the 720x480 minimum layout.

## Settings contract

`desktop/src/screens/settings/registry.json` is the structural settings inventory. `tests/unit/test_settings_coverage.py` recursively compares it with every `DaxConfig` leaf. Secrets render as replaceable password fields, remain blank on GET, and are never returned in clear text.

## Verification

Run all gates listed in `AGENTS.md`. Automated tests do not replace these physical checks:

- Human visual review of the surface steps, custom/native chrome, orb, and all screens.
- Real microphone, speaker, wake-word, and Kokoro input/output visualization.
- Remote audio between two hosts.
- Wayland frame, resize, and HUD behavior.
- Final CPU/PSS profiling after idle settles.
- Clean RPM and deb installation.
