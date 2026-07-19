# Desktop Architecture

This document is the implementation map for Dax Desktop. `AGENTS.md` contains the short operational rules; this file records the boundaries and invariants that future work must preserve.

## Process boundaries

Dax Desktop has three layers:

1. The Python backend owns conversations, agent orchestration, MCP, policy, configuration, persistence, STT, TTS, and the voice state machine.
2. The Tauri Rust core owns OS capabilities: windows, tray, global shortcuts, autostart, notifications, systemd control, host metrics, keyring access, and validated local preferences.
3. The React webview owns presentation and backend protocols. It calls FastAPI directly; Rust is not an HTTP proxy.

HTTP uses bearer authentication. WebSockets use the same token as an authenticated query parameter because the browser WebSocket API cannot set an Authorization header. Remote origins require HTTPS/WSS. Plain HTTP/WS is accepted only for loopback.

## Connection strategy

Rust persists a versioned connection document. Schema v2 contains:

- `strategy`: `local`, `remote`, or `hybrid`.
- `local_url`: a validated loopback URL.
- `remote_url`: a validated HTTPS URL when remote access is configured.
- `active_url`: the origin selected by the latest explicit resolution.
- `onboarding_complete`: whether first-run setup has been accepted.

The legacy v1 `{mode,url}` document is migrated to schema v2 on read and then
rewritten atomically.

Resolution rules are deterministic:

- Local probes only `local_url`.
- Remote probes only `remote_url` and never silently falls back.
- Hybrid probes remote first and loopback second.
- Starting `dax-assistant.service` requires explicit consent and is attempted only for the local candidate.
- Three confirmed runtime failures may trigger hybrid fallback. There is no automatic failback during an active session; remote can be reconsidered manually or on the next launch.

Tokens are stored per URL origin. Changing `active_url` shuts down realtime stores, loads the token for the new origin, and restarts authentication. A remote credential must never be sent to local Dax or another server.

## First-run onboarding

Native desktop launches onboarding before authentication when `onboarding_complete` is false. Browser-only development skips native setup.

The flow covers:

1. Privacy and where conversations are processed.
2. Local, server-only, or hybrid strategy.
3. URL validation and connectivity checks.
4. Detection and optional start of the existing systemd user service.
5. Review and atomic persistence.

The desktop package does not silently install the Python backend. Missing service state is reported honestly. The same strategy editor remains available in Desktop Settings and from the unreachable-backend screen. It can reconfigure local, remote, or hybrid mode, validate both URLs, and request consent before starting `dax-assistant.service`; reconfiguration never copies a token between origins.

## Realtime stores

Voice and logs use one demand-managed external store per webview window. Chat uses one isolated store per `session_id`. Stores survive route changes, close on logout/pagehide, keep bounded buffers, and reject frames belonging to another chat session.

`/ws/voice` carries state, user transcripts, the current synthesized `speech`
sentence, speaker verdict, errors, and level frames. Kokoro emits each `speech`
sentence after synthesis and immediately before playback, so the command deck
and HUD replace the user transcript with what Dax is audibly saying. Level data
always preserves `source: input|output`:

- `input` is microphone energy.
- `output` is TTS playback energy, including Kokoro.

Remote microphone input is an authenticated exclusive lease. It accepts bounded PCM16LE, 16 kHz, mono frames during push-to-talk only. TTS audio is still played on the backend host; the current contract does not stream output audio to the desktop.

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

The current recorded automated gate is 316 backend tests, 61 frontend tests, and
26 Rust tests. `npm audit --omit=dev` reports 0 vulnerabilities; the frontend
build and ruff, mypy, and clippy checks are clean.

Run all gates listed in `AGENTS.md`. Automated tests do not replace these physical checks:

- Human visual review of the surface steps, custom/native chrome, orb, and all screens.
- Real microphone, speaker, wake-word, and Kokoro input/output visualization.
- Remote audio between two hosts.
- Wayland frame, resize, and HUD behavior.
- Final CPU/PSS profiling after idle settles.
- Clean RPM and deb installation.
