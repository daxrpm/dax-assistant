# Dax Desktop

The first-class Linux client, built with Tauri v2, React 19, and TypeScript. It
calls the authoritative Python backend directly over HTTP/WebSocket and does not
embed a Python sidecar or proxy application traffic through Rust. See
[`../docs/desktop-architecture.md`](../docs/desktop-architecture.md) for the
architectural invariants.

## Implemented Surface

- Session-isolated chat with persisted conversations, Markdown, agent activity,
  tool approvals, and strict `session_id` correlation.
- Searchable declarative Settings covering every `DaxConfig` leaf, MCP and
  devices, logs, host metrics, and allowlisted systemd controls.
- Command-deck home, command palette, tray, global shortcuts, autostart, native
  notifications, custom/native main-window chrome, and a separate voice HUD.
- Canvas 2D voice rendering with imperative, bounded input/output level buffers;
  high-rate frames do not pass through React state.
- Local backend-host voice and remote PTT microphone input as PCM16LE 16 kHz mono
  over `/ws/voice`. Default server output plays on the backend host. A
  `client_text` lease emits text and suppresses server synthesis/playback; the
  desktop currently uses server output. Streaming synthesized audio back to the
  desktop is not implemented.
- Spanish and English UI, responsive layouts, lazy screen chunks, and
  demand-managed realtime stores.

The browser, desktop, and Android surfaces share backend capabilities and wire
contracts, but they are not pixel-identical. Desktop intentionally owns Linux
windowing, tray, shortcuts, keyring, host metrics, local systemd controls, media
integration, and the voice HUD. Business logic and persisted state remain on the
backend.

## First Run And Authority

Native onboarding completes before authentication. It explains processing and
privacy, selects `local` or `remote`, validates connectivity, and asks before
starting the existing local `dax-assistant.service`.

- `local` deliberately selects the laptop's validated loopback service as the
  one authoritative backend. It is not a fallback target.
- `remote` selects one validated HTTPS backend. It never falls back to loopback.
- Remote HTTP/WS is rejected; non-loopback connections require HTTPS/WSS.

Rust connection settings use schema v3. Schema-v2 local and remote settings keep
their meaning; historical schema-v2 `hybrid` settings migrate to `remote` using
their configured `remote_url`, with no fallback behavior. Legacy v1 settings are
also migrated and rewritten atomically.

Health resolution accepts only a ready Dax API reporting `role=authoritative`,
`api_protocol=dax`, a compatible API version, and a non-empty `instance_id`.
Tokens are stored in the OS keyring by normalized origin plus `instance_id`.
Changing either identity closes realtime stores and never reuses the previous
credential.

The optional laptop capability node is independent from connection strategy.
Create its enrollment code in the paired-devices UI, then follow
[`../docs/capability-nodes.md`](../docs/capability-nodes.md). Running a node does
not make this desktop a backend.

## Requirements And Development

Fedora build dependencies:

```bash
sudo dnf install webkit2gtk4.1-devel openssl-devel curl wget file \
  libappindicator-gtk3-devel librsvg2-devel libxdo-devel gcc gcc-c++ make
```

Rust stable and Node 22 LTS are also required. Install and operate the backend
separately as described in the root `README.md`.

```bash
cd desktop
npm install
npm run tauri dev
```

Packaged webviews use trusted Tauri origins configured by the backend. The Vite
development origin is `http://localhost:5273` and may need an explicit
development CORS entry. A plain `cargo build` does not embed `dist/`; use
`npm run tauri dev` or `npm run tauri build`.

## Verification

From the repository root:

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src

cd desktop
npm run typecheck
npm test
npm run build
npm audit --omit=dev

cd src-tauri
cargo fmt --all -- --check
cargo test --all-targets --all-features
cargo clippy --all-targets --all-features -- -D warnings
```

Do not infer hardware or packaging success from automated checks. Real
microphone/speaker/wake-word behavior, two-host remote PTT, visual/accessibility
review, Wayland HUD placement, final CPU/PSS profiling, signing, and clean RPM or
deb install/uninstall are separate gates.

## Packages

```bash
cd desktop
npm run tauri build
npm run tauri build -- --bundles rpm
npm run tauri build -- --bundles deb
```

RPM and deb are the supported desktop targets; AppImage and Flatpak are not
configured. Linux packages do not contain or install the Android APK. Tagged
release artifacts and their attestation flow are documented in
[`../docs/releases.md`](../docs/releases.md).
