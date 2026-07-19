# Dax Desktop

Native desktop client for the Dax assistant. Tauri v2 + React 19 + TypeScript.

`PLAN.md` is the authoritative design document. Milestones **M0** and **M1** are
complete; see the "RESULTS" blocks in its section 10 for what was measured.

## Prerequisites

Fedora 44:

```bash
sudo dnf install webkit2gtk4.1-devel openssl-devel curl wget file \
  libappindicator-gtk3-devel librsvg2-devel libxdo-devel gcc gcc-c++ make
```

Plus Rust stable and Node 22 LTS.

## Backend configuration — required

The desktop app connects to an already-running backend (default
`http://127.0.0.1:8420`). **The backend must allow the webview origin**, or every
request fails CORS preflight and the app reports "Backend unreachable":

```toml
[web]
cors_origins = ["tauri://localhost"]        # packaged app
# add "http://localhost:5273" when running `npm run tauri dev`
```

Start the backend with `uv run dax` or the systemd user unit.

## Develop

```bash
npm install
npm run tauri dev     # Vite dev server + Tauri window, hot reload
npx tsc -b            # typecheck
```

## Build

```bash
npm run tauri build                  # all configured bundles
npm run tauri build -- --bundles rpm # just the RPM
```

Output lands in `src-tauri/target/release/bundle/`. RPM and deb build cleanly;
AppImage currently fails at the `linuxdeploy` step (deferred to M6).

## Gotchas

- **A plain `cargo build` debug binary does not embed the frontend** — Tauri
  points it at `devUrl`. Running it without a Vite dev server gives a blank
  window and no network traffic, which looks deceptively like a CSP or CORS
  problem. Use `npm run tauri dev` or `npm run tauri build`.
- `cargo build` does not rebuild when only `dist/` changed.
- CSP `connect-src` is baked in at build time and currently allows loopback on
  any port. Pointing the app at a **remote** backend host requires editing
  `src-tauri/tauri.conf.json`.
- Wayland ignores programmatic window positioning and exact sizing — relevant to
  the M4 voice HUD.

## Auth

Login returns a signed session token in the response body. The desktop client
stores it in the OS keyring (via Rust) and sends
`Authorization: Bearer <token>` on HTTP and `?token=<token>` on WebSockets, since
a `SameSite=lax` cookie is not dependable from the `tauri://localhost` origin.
The browser SPA's cookie flow is unchanged.
