# Dax Desktop — Implementation Plan

**Status:** Planning complete, zero code written.
**Document version:** 1 (2026-07-18)
**Target:** a native desktop client for Dax, in this repo at `desktop/`.

> **Read this first if you are a cold agent.** This document is the single source of
> truth for the desktop app. It is written to be executed without any prior
> conversation context. Section 13 ("How to continue this work") tells you exactly
> where to start. Section 2 lists decisions that are **closed** — do not reopen them.
> Anything genuinely uncertain is marked **UNCERTAIN** inline; treat those as
> research tasks, not as settled fact.

---

## 1. Executive summary and current status

### 1.1 What we are building

A desktop application for Dax — the self-hosted single-user AI assistant whose
backend lives in this repo under `src/dax/`. Today the only UI is a React SPA
(`web/`, 6,411 lines of TS/TSX) that FastAPI serves from
`src/dax/web/static/`. The desktop app is a **second, first-class client** against
the same backend, with a native shell, a macOS-inspired design language, and a
voice UI the browser cannot deliver well.

The backend is **not** being rewritten. The desktop app talks to the same 52 HTTP
routes and 2 (soon 3) WebSocket endpoints the web SPA uses. See section 4 for the
complete contract.

### 1.2 Why a desktop app at all

Three things the browser SPA cannot do well:

1. **Always-available voice.** Global hotkey, tray presence, a persistent
   always-on-top voice HUD, OS notifications. A browser tab is a poor host for a
   wake-word assistant.
2. **Lifecycle ownership.** The desktop app can *run the backend itself* as a
   sidecar process, so "launch Dax" is one action instead of "start systemd unit,
   then open a tab".
3. **Native feel.** Window chrome, menus, native file dialogs, no browser UI.

### 1.3 Current status of prerequisites

| Item | Status |
| --- | --- |
| Backend HTTP API | Done — 52 routes, stable |
| `/ws/chat` protocol | Done — `src/dax/web/routes/chat.py` |
| `/ws/logs` protocol | Done — `src/dax/web/routes/logs.py` |
| `/ws/voice` protocol | **NOT BUILT** — see 4.5, this is a backend prerequisite |
| `VoiceEventHub` | Done — `src/dax/core/voice_events.py` |
| Voice DSP metering | Done — `src/dax/voice/events.py` |
| Pipeline event emission | Done — `src/dax/voice/pipeline.py` |
| Hub wired into app | Done — `src/dax/app.py`, `app.state.voice_events` |
| `desktop/` directory | **M0 + M1 complete** (2026-07-18) — scaffold, design system, shell, login, dashboard, tray, keyring |
| Bearer-token auth | **Done** — `src/dax/web/auth.py`, `routes/auth.py`, 13 tests |
| Fedora build deps | **All installed** — verified via `rpm -q` |

### 1.4 Verified environment (checked 2026-07-18 on this machine)

```
Fedora release 44 (Forty Four)
rustc 1.96.0 (ac68faa20 2026-05-25)
cargo 1.96.0 (30a34c682 2026-05-25)
node v22.22.2
```

Installed: `webkit2gtk4.1-devel-2.52.5-1.fc44`, `libsoup3-devel-3.6.6-8.fc44`,
`webkit2gtk4.1-2.52.5`, `libsoup3-3.6.6-8`, `gtk3-devel-3.24.52-1.fc44`,
`openssl-devel-3.5.7-1.fc44`.

**Missing:** `librsvg2-devel`, `libxdo-devel`, `libappindicator-gtk3-devel`.

Target triple (verified via `rustc --print host-tuple`): **`x86_64-unknown-linux-gnu`**.
Sidecar binaries must therefore be named `dax-backend-x86_64-unknown-linux-gnu`.

> **Correction to the original brief.** The task brief stated that
> `webkit2gtk4.1-devel` and `libsoup3-devel` were *not* installed. They **are**
> installed (verified with `rpm -q`). The actual gaps are `librsvg2-devel` and
> `libxdo-devel`. See 11.1.

---

## 2. Decisions already made — CLOSED

Do not reopen these. They were decided by the user. Rationale is recorded so
nobody has to re-derive it.

### D1. Stack: Tauri v2 + Rust core + web-tech UI

Chosen over GPUI, Iced, and Electron.

- **vs Electron:** memory. Tauri on Linux uses the system WebKitGTK rather than
  bundling Chromium. Published comparisons put Tauri idle around 30–50 MB against
  Electron's 150–300 MB, i.e. roughly 50–75% lower. Our own budget (D5) is
  90–140 MB for the *whole* desktop app under real use.
  **Caveat, recorded honestly:** WebKitGTK is not universally lighter than
  Chromium — there are reported workloads where WebKit uses >90 MB more than
  Chromium for the same page. The savings come mostly from not shipping a second
  browser engine, not from WebKit being intrinsically frugal. Section 12 lists
  measuring this as an open item.
- **vs GPUI / Iced:** feature parity cost. The UI surface is large — markdown
  rendering with GFM tables, syntax highlighting, and roughly 30 configuration
  forms across 9 screens. Rebuilding markdown + highlighting + form widgets in a
  native immediate-mode toolkit is months of work with no user-visible benefit.
- **Rust core** satisfies the user's stated preference for Rust and is where
  process supervision, the tray, global hotkeys, and secure token storage live.

### D2. Location: same repo, new top-level `desktop/` directory

Monorepo. The API contract changes in lockstep with the backend, and TypeScript
types are shared. A separate repo would require versioned contract releases for a
single-user app — pure overhead.

### D3. Design language: modern macOS (Tahoe/Sonoma-era), NOT a copy of `web/`

Translucent sidebar, hairline separators, an SF-like type stack, spring easings,
vibrancy where the platform allows, minimalist components. The user's reference
point: "estilo Claude Code app". **Must work well on Linux** — this is a Fedora 44
machine and it is the primary target. Section 5 specifies the tokens. Section 3.6
is honest about which macOS effects are unachievable on Linux.

### D4. Voice audio: Python pipeline stays server-side; the audio *source* becomes pluggable

Do **not** rewrite STT, TTS, or wake-word detection in Rust. The architecture is:

- `LocalAudioSource` — the existing `sounddevice` capture, used when Tauri runs
  the backend as a sidecar on the same machine. This is the default and covers
  the primary use case.
- `RemoteAudioSource` — PCM streamed from the desktop client over a WebSocket,
  used when the desktop connects to a backend on another host.

The pipeline (`src/dax/voice/pipeline.py`) does not care which it gets. See 7.6.

### D5. Performance is a hard requirement — REVISED 2026-07-18

**The original 90–140 MB RSS budget was wrong and has been retired.** It was
derived from Tauri's cross-platform marketing figures, which do not hold for
WebKitGTK on Linux. M0 measured the real floor, and the user accepted it.

**Measured at M0** (release build, idle on the login screen, zero features),
confirmed by two independent measurements:

| Process | RSS | PSS |
|---|---|---|
| `dax-desktop` | 157 MB | 70 MB |
| `WebKitWebProcess` | 194 MB | 111 MB |
| `WebKitNetworkProcess` | 60 MB | 19 MB |
| **Total** | **417 MB** | **202 MB** |

**Track PSS, not RSS.** RSS counts shared system libraries (WebKitGTK, GTK,
glibc) in full against each of the three processes, though they exist once in
physical memory and are shared with every other GTK app running. PSS divides
those pages proportionally and is the honest measure of what the app costs the
machine. Electron ships its own Chromium and shares nothing, so its PSS ≈ its
RSS ≈ 300–500 MB; Tauri is roughly 2× better here, not the 3–4× commonly
claimed.

**Revised budget: 250 MB PSS** for the full-featured app, up from 202 MB
measured empty. The binary is 6.3 MB — this is WebKitGTK's floor, not our code,
and there is nothing to optimize away (R4's original fallback of "reduce
in-memory buffers" is void: at M0 there are no buffers).

Voice waveform rendering must still idle at approximately **0% CPU** when the
pipeline is idle — that part of D5 stands unchanged and is achievable. Section
6.4 specifies how; section 10 makes it a per-milestone gate.

**Consequence for later milestones:** measure PSS at every gate. If the full app
exceeds 250 MB PSS, that is a signal to virtualize long lists (Logs, chat
history) — not to revisit D1, which the user explicitly declined to reopen.

---

## 3. Architecture

### 3.1 Process model

```
┌─────────────────────────────────────────────────────────────┐
│ dax-desktop  (Tauri v2 app, one OS process + webview procs) │
│                                                             │
│  ┌───────────────────────┐      ┌────────────────────────┐  │
│  │ Rust core             │ IPC  │ Webview (WebKitGTK)    │  │
│  │  - window mgmt        │◄────►│  - UI framework        │  │
│  │  - tray icon          │invoke│  - all screens         │  │
│  │  - global hotkey      │event │  - HTTP + WS clients   │  │
│  │  - sidecar supervisor │      │  - waveform canvas     │  │
│  │  - token storage      │      │                        │  │
│  │  - autostart          │      │                        │  │
│  └───────────┬───────────┘      └───────────┬────────────┘  │
└──────────────┼──────────────────────────────┼───────────────┘
               │ spawn / stdout               │ HTTP + WebSocket
               │                              │ (127.0.0.1:8420)
        ┌──────▼──────────────────────────────▼──────┐
        │ Python backend  (uv run dax)               │
        │  sidecar-managed (local) OR remote (URL)   │
        │  FastAPI + agent loop + MCP + voice        │
        └────────────────────────────────────────────┘
```

**Key point:** the webview talks to the backend over plain HTTP/WebSocket, exactly
as the browser SPA does. It does **not** proxy API calls through Rust IPC. This
means:

- `web/src/api/client.ts` (380 lines) ports with a one-line change: `BASE`
  becomes an absolute origin instead of `/api`.
- The existing cookie-based auth works unchanged **if** cookies survive the
  cross-origin webview context — see 3.5, this is the single riskiest integration
  point.
- No IPC serialization overhead on the hot path (chat streaming, log streaming,
  voice level frames at ~12.5 Hz).

### 3.2 What lives in Rust

Rust owns everything the webview cannot do or should not be trusted with:

| Responsibility | Why Rust |
| --- | --- |
| Backend sidecar supervision | Spawn, health-check, restart, graceful shutdown, capture stdout/stderr |
| Backend mode switching | Local sidecar vs remote URL; persist choice |
| Session token storage | Keyring / OS secret store, not `localStorage` |
| Tray icon + menu | Platform API |
| Global hotkey (push-to-talk / summon) | Platform API |
| Window management | Main window, voice HUD overlay window, always-on-top |
| Autostart on login | Platform API |
| Native notifications | Platform API |
| Single-instance enforcement | Second launch focuses the existing window |
| Deep links (`dax://`) | Optional, later |

**Rust does NOT own:** any API call shape, any business logic, any rendering. If
you find yourself writing a Rust command that proxies `GET /api/config`, stop —
that belongs in the webview's HTTP client.

### 3.3 What lives in TypeScript

Everything visual and everything protocol-level:

- All 9+ screens (section 6)
- The HTTP client (ported from `web/src/api/client.ts`)
- All three WebSocket clients (`/ws/chat`, `/ws/logs`, `/ws/voice`)
- Markdown rendering, syntax highlighting
- The waveform renderer (Canvas 2D — section 7.4)
- The design system (section 5)

### 3.4 IPC boundaries

Tauri IPC is used for a deliberately small command surface. Proposed commands
(names are a proposal; adjust freely during implementation):

```
backend_status()        -> { mode: "sidecar"|"remote", running: bool,
                             url: string, pid: number|null, healthy: bool }
backend_start()         -> Result<()>
backend_stop()          -> Result<()>
backend_restart()       -> Result<()>
backend_set_mode(mode, url?) -> Result<()>

session_token_get()     -> Option<String>
session_token_set(tok)  -> Result<()>
session_token_clear()   -> Result<()>

open_voice_hud()        -> Result<()>
close_voice_hud()       -> Result<()>

set_autostart(enabled)  -> Result<()>
get_autostart()         -> bool
```

Rust → TS events (emitted on the Tauri event bus):

```
backend://stdout   { line: string }
backend://stderr   { line: string }
backend://state    { running: bool, healthy: bool, exit_code: number|null }
hotkey://push-to-talk-down
hotkey://push-to-talk-up
hotkey://summon
tray://show-voice-hud
```

**Rule:** every new IPC command must justify why it cannot be an HTTP call to the
backend.

### 3.5 Auth across the IPC/origin boundary — the highest-risk item

The backend authenticates with a signed cookie (`src/dax/web/auth.py:114-123`,
`samesite="lax"`, `secure=config.cookie_secure`) and additionally accepts a
`?token=` query parameter on WebSocket handshakes
(`src/dax/web/auth.py:144-151`):

```python
def authenticate_websocket(self, websocket: WebSocket) -> bool:
    if not self._enabled:
        return True
    token = websocket.cookies.get(self.cookie_name)
    if not token:
        token = websocket.query_params.get("token")
    return self.validate_token(token)
```

The Tauri webview loads the UI from a `tauri://` (Linux: custom protocol) origin,
not from `http://127.0.0.1:8420`. Cookies set by the backend on a cross-origin
`fetch` may or may not be stored and replayed by WebKitGTK, depending on
`credentials` mode, `SameSite=lax`, and WebKit's third-party cookie policy.

**UNCERTAIN — must be validated in Milestone 0.** Do not build on the assumption
that cookies work.

**Planned mitigation (recommended, low-risk):** add a bearer-token path.
`src/dax/web/auth.py:130` already has a `_token_from_headers` helper that reads
the cookie; extend it to also accept `Authorization: Bearer <token>`, and have
`POST /api/auth/login` return the token in the JSON body in addition to setting
the cookie. Then:

- Desktop stores the token in the OS keyring via Rust.
- HTTP calls send `Authorization: Bearer <token>`.
- WebSocket calls append `?token=<token>` — **already supported, no backend
  change needed**.

This is a small, backwards-compatible backend change. It removes all cookie
ambiguity and is strictly better for a desktop client. Treat it as part of
Milestone 1.

> Security note: `?token=` in a WebSocket URL is acceptable here because the
> connection is to `127.0.0.1` (or a user-configured host) and the URL is not
> logged by the browser history in a webview. If the user configures a remote
> backend over plain HTTP, warn them.

### 3.6 Window vibrancy and transparency — honest Linux assessment

**This contradicts nothing in D3, but it constrains it. Read carefully.**

Research finding: `tauri-apps/window-vibrancy` — the canonical crate for this —
supports macOS (`NSVisualEffectView`) and Windows (Acrylic/Mica/blur).
**On Linux, blur and vibrancy are unsupported.** They are controlled entirely by
the end user's compositor. An application cannot programmatically request them.

Wayland adds a second constraint: there is no equivalent of X11's
`_GTK_FRAME_EXTENTS`, so with `decorations: false` the compositor strips frame
hints and CSS box-shadows get clipped at the window edge.

**What is actually achievable on Fedora 44 (GNOME/Wayland):**

| Effect | Wayland | X11 | Notes |
| --- | --- | --- | --- |
| True backdrop blur behind window | ❌ | ❌ | Compositor-controlled; not app-requestable |
| Window transparency (`transparent: true`) | ✅ | ✅ | Alpha compositing works |
| Borderless / custom titlebar | ✅ | ✅ | `decorations: false` |
| CSS shadow outside window bounds | ❌ (clipped) | ⚠️ via `_GTK_FRAME_EXTENTS` | Workaround: transparent window + CSS margin equal to shadow radius |
| Rounded window corners | ✅ | ✅ | Via transparency + CSS `border-radius` |
| Native window controls | ✅ | ✅ | Keep `decorations: true`, or draw our own |

**Design consequence — this is the important part.** The "translucent sidebar" in
D3 must be implemented as a **layered-opacity design**, not a blur:

- Sidebar background: a semi-opaque fill over the window background
  (`rgba` with a subtle gradient), reading as "lighter/recessed" rather than
  "see-through".
- On macOS (if ever targeted), conditionally enable real `NSVisualEffectView`
  vibrancy behind the same sidebar via `window-vibrancy`, and drop the fallback
  fill. Same component, platform-conditional treatment.
- Do not ship a design that only reads correctly with blur. It will look flat and
  wrong on the primary target machine.

**Recommendation for Fedora/Wayland:** ship with `decorations: true` initially
(native GNOME titlebar, correct window controls, correct shadows, correct
resize handles) and treat the custom titlebar as a later, optional milestone.
Fighting Wayland decorations early will cost days for cosmetic gain.

### 3.7 Sidecar: bundling the Python backend

Tauri v2 supports external binaries via `bundle.externalBin` in
`tauri.conf.json`:

```json
{
  "bundle": {
    "externalBin": ["binaries/dax-backend"]
  }
}
```

**Hard requirement:** each binary must exist on disk with a `-$TARGET_TRIPLE`
suffix. On this machine that is `dax-backend-x86_64-unknown-linux-gnu`. Get the
triple with `rustc --print host-tuple`.

Permission is granted in `src-tauri/capabilities/default.json`:

```json
{
  "permissions": [
    "core:default",
    {
      "identifier": "shell:allow-execute",
      "allow": [{ "name": "binaries/dax-backend", "sidecar": true }]
    }
  ]
}
```

Spawning from Rust (this is the pattern; adapt during implementation):

```rust
use tauri_plugin_shell::ShellExt;
let cmd = app.shell().sidecar("dax-backend")?;
let (mut rx, mut child) = cmd.spawn()?;
// consume CommandEvent::Stdout / Stderr / Terminated from rx
```

**The problem: Dax is a Python app, not a single binary.** Three options:

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| **A. Shell-script shim** calling `uv run dax` | Trivial; always matches the repo; dev-friendly | Requires `uv` + a synced `.venv` on the user's machine; not distributable | **Use for Milestones 0–4** |
| **B. PyInstaller / Nuitka one-file bundle** | Real self-contained distributable | Large (voice extra pulls numpy, onnxruntime, torch-adjacent deps → likely 300 MB–1 GB); brittle with native deps | Evaluate at Milestone 6 |
| **C. No sidecar; user runs the systemd unit** | Zero packaging work; matches today's deployment (`scripts/install.sh`) | Loses the "one launch" benefit | **Ship as a supported mode** |

**Recommendation:** implement **C as the default fallback** and **A as the dev
path**, with the backend-mode switch (3.4) exposing both. `backend_set_mode`
takes `"sidecar" | "remote"`; "remote" pointed at `http://127.0.0.1:8420` is
exactly the systemd case and requires no sidecar at all. Defer B until there is a
reason to distribute to someone who is not the author.

This ordering means **the app is useful from Milestone 1 without solving Python
packaging at all**, which is the right risk profile.

### 3.8 Tauri v2 capabilities/permissions model

Capability files live in `src-tauri/capabilities/*.json` (or `.toml`). Structure:

```json
{
  "identifier": "main-capability",
  "description": "Permissions for the main window",
  "windows": ["main"],
  "platforms": ["linux", "macOS", "windows"],
  "permissions": ["core:default", "core:window:allow-set-title"]
}
```

- `identifier` — unique name
- `windows` — window **labels** (not titles) this applies to
- `permissions` — array; entries are either strings (`plugin:action`) or objects
  with `allow`/`deny` scope arrays
- `platforms` — optional OS filter
- `remote.urls` — for granting permissions to remotely-loaded content

Permissions follow `plugin:action:scope` naming. By default all registered Rust
commands are reachable from all windows; restrict via `AppManifest::commands()`
in the build script.

> **Security caveat from the docs, relevant to us:** on Linux and Android, Tauri
> cannot distinguish iframe requests from window requests. Since we render
> LLM-produced markdown, **do not render untrusted HTML into an iframe**. Keep
> markdown rendering sanitized and iframe-free.

**Capabilities we will need:**

| Capability | For |
| --- | --- |
| `core:default` | Baseline |
| `core:window:*` | Voice HUD window, always-on-top, positioning |
| `shell:allow-execute` (scoped to the sidecar) | Backend sidecar (Option A/B only) |
| `shell:allow-open` | Opening OAuth URLs in the system browser |
| `clipboard-manager:allow-write-text` | "Copy Codex config" / "Copy Claude config" |
| `notification:default` | Native notifications |
| `global-shortcut:*` | Push-to-talk, summon |
| `dialog:*` | File pickers (voice enrollment, model paths) |
| `os:default` | Platform detection for conditional styling |
| `store` or `keyring` | Persisting backend mode + session token |

Grant the **narrowest** scope that works. Do not ship `shell:allow-execute` with
an open scope.

### 3.9 Directory layout

```
desktop/
├── PLAN.md                     (this file)
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/                        (webview UI)
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts           ← ported from web/src/api/client.ts
│   │   ├── config.ts           ← backend base URL + token resolution
│   │   └── types.ts            ← shared with web/ (see note)
│   ├── ws/
│   │   ├── useChatSocket.ts    ← ported from web/src/hooks/useChatSocket.ts
│   │   ├── useLogSocket.ts
│   │   └── useVoiceSocket.ts   ← NEW
│   ├── design/                 ← the design system (section 5)
│   │   ├── tokens.css
│   │   └── primitives/
│   ├── screens/
│   ├── components/
│   └── lib/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/
│   │   └── default.json
│   ├── binaries/               ← sidecar shims, gitignored except the shim source
│   ├── icons/
│   └── src/
│       ├── main.rs
│       ├── backend.rs          ← sidecar supervisor
│       ├── tray.rs
│       ├── hotkeys.rs
│       ├── secrets.rs
│       └── windows.rs
└── shared/                     ← optional: types shared with web/
```

**Shared types note.** The cleanest option is a `shared/api-types.ts` consumed by
both `web/` and `desktop/` via a relative path or a workspace package. This is
worth doing but is **not** a Milestone 1 blocker — start by copying
`web/src/types/config.ts` (157 lines) and `web/src/api/client.ts` interfaces, and
unify in Milestone 5. Copying first avoids coupling two build systems before
either works.

---

## 4. Complete backend API contract reference

**Sources of truth:** `src/dax/web/routes/*.py` and `web/src/api/client.ts`.
**Totals:** 52 HTTP routes + 2 existing WebSocket routes + 1 planned = 55 endpoints.
The "54 routes" figure in the brief = 52 HTTP + 2 WS.

### 4.1 Mounting and auth (`src/dax/web/server.py:78-96`)

```
/api/*            auth router      — PUBLIC (login/logout/status/setup/health)
/api/*            system, config, mcp, conversations, memory, voice
                                   — PROTECTED via Depends(require_auth)
/api/*            oauth            — PROTECTED
/ws/chat          chat             — authenticates in its own handshake
/ws/logs          logs             — authenticates in its own handshake
/webhook/*        webhooks         — secret-based
/                 SPA static files
```

Default bind: `127.0.0.1:8420`.

CORS (`server.py:69-77`) allows `config.web.cors_origins`, plus
`http://localhost:5173` when `config.web.dev_mode` is true.
**Desktop implication:** the Tauri webview's origin must be added to
`cors_origins`, OR the bearer-token approach (3.5) must be used, OR
`dev_mode` must be on during development. Plan on adding the Tauri origin to
`cors_origins` — this is a config change, not a code change.

### 4.2 HTTP routes — complete enumeration

#### `auth.py` — 5 routes, PUBLIC

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | `HealthResponse` |
| GET | `/api/auth/status` | `{ auth_enabled, configured, authenticated }` |
| POST | `/api/auth/setup` | First-run account creation; `{ password }` → `{ ok }` |
| POST | `/api/auth/login` | `{ password }` → `{ ok }`, sets cookie |
| POST | `/api/auth/logout` | Clears cookie |

#### `system.py` — 8 routes

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/status` | `StatusResponse` — see 4.3 |
| POST | `/api/voice/toggle` | `{ enabled }` → `{ voice_listening }` |
| GET | `/api/logs?limit=200` | `LogEntry[]` |
| GET | `/api/mcp/status` | `MCPServerStatus[]` |
| GET | `/api/tools/audit?limit=50` | `ToolAuditEntry[]` |
| GET | `/api/tools/policy` | `ToolPolicyResponse` |
| GET | `/api/ollama/models` | `OllamaModel[]` |
| GET | `/api/llm/models?provider=` | `Record<string, string[]>` |

#### `config.py` — 11 routes

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/config` | Full config, **secrets masked** |
| PATCH | `/api/config/general` | |
| POST | `/api/config/general/system-prompt/reset` | → `{ status, system_prompt }` |
| PATCH | `/api/config/llm` | Rebuilds the LLM router in place, no restart |
| PATCH | `/api/config/voice` | Triggers `reload_voice()` |
| PATCH | `/api/config/whatsapp` | |
| PATCH | `/api/config/web` | Host/port need a restart |
| PATCH | `/api/config/telegram` | Needs a restart |
| PATCH | `/api/config/tools` | Applies live via `policy.reload` |
| PATCH | `/api/config/security` | |
| POST | `/api/auth/change-password` | `{ current_password, new_password }` |

> **Masking convention (critical).** `GET /api/config` returns secret fields
> masked. `PATCH` restores unchanged masks server-side. The desktop UI must
> replicate the web UI's behavior: send back the mask verbatim to mean
> "unchanged", send a real value to mean "replace". Reference:
> `web/src/pages/settings/VoiceTab.tsx:185` shows the `stt_openai_configured`
> boolean pattern used to render "Configured. Leave blank to keep the stored key."

#### `mcp.py` — 11 routes

| Method | Path |
| --- | --- |
| GET | `/api/config/mcp/servers` |
| POST | `/api/config/mcp/servers` |
| POST | `/api/config/mcp/servers/{server_name}/reconnect` → `{ status, tools }` |
| PATCH | `/api/config/mcp/servers/{server_name}` |
| DELETE | `/api/config/mcp/servers/{server_name}` |
| GET | `/api/config/system/shell-allow` → `{ commands, default }` |
| PUT | `/api/config/system/shell-allow` `{ commands }` |
| GET | `/api/codex-config` → `{ toml, server_count, note }` |
| GET | `/api/claude-config` → `{ json, server_count, note }` |
| GET | `/api/mcp/presets` → `MCPPreset[]` |
| GET | `/api/mcp/registry/search?q=&limit=30` → `{ servers, count?, error? }` |

#### `conversations.py` — 3 routes

| Method | Path |
| --- | --- |
| GET | `/api/conversations?limit=50` → `ConversationSummary[]` |
| GET | `/api/conversations/{id}` → `ConversationDetail` |
| DELETE | `/api/conversations/{id}` → 204 |

#### `memory.py` — 5 routes

| Method | Path |
| --- | --- |
| GET | `/api/memory` → `MemoryEntry[]` |
| GET | `/api/memory/{slug}` → `MemoryEntry` |
| POST | `/api/memory` → 201, `MemoryEntry` |
| PATCH | `/api/memory/{slug}` → `{ status }` |
| DELETE | `/api/memory/{slug}` → 204 |

#### `voice.py` — 4 routes, prefix `/api/voice`

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/voice/profile` | `{ enrolled: bool }` |
| POST | `/api/voice/enroll` | **multipart/form-data**, field `samples`, 3–5 WAV files. `_MIN_SAMPLES`/`_MAX_SAMPLES` enforced; 422 on violation, 503 if the Voice ID model is unavailable |
| DELETE | `/api/voice/profile` | Deletes `voice_profile.npy`, reloads voice |
| POST | `/api/voice/preview` | JSON body → **`audio/wav` blob**. Engines: `kokoro`, `piper`, `openai` |

#### `oauth.py` — 4 routes

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/mcp/{name}/auth/start` | → `{ authorization_url, state }`; open in the **system browser** |
| GET | `/api/mcp/oauth/callback` | Backend handles; reconnects the server so the token takes effect |
| GET | `/api/mcp/{name}/auth/status` | → `{ authenticated, expired? }` |
| POST | `/api/mcp/{name}/auth/logout` | |

> **Desktop implication.** The OAuth callback returns to the *backend*, not the
> app. The desktop must open `authorization_url` in the system browser
> (`shell:allow-open`) and then poll `/api/mcp/{name}/auth/status` until
> `authenticated` is true. Do not try to intercept the callback in the webview.

#### `webhooks.py` — 1 route

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/webhook/whatsapp` | Evolution API inbound. Not used by the desktop. |

### 4.3 Key response shapes

From `src/dax/web/routes/system.py:20-28` and `web/src/api/client.ts`:

```ts
interface StatusResponse {
  name: string; version: string; status: string;
  voice_listening: boolean; llm_provider: string;
  mcp_servers: number; mcp_tools: number;
}

interface MCPServerStatus {
  name: string; connected: boolean; transport: string;
  enabled: boolean; tool_count: number; tools: string[];
}

interface ToolPolicyResponse {
  default: string; allow: string[]; ask: string[]; deny: string[];
  confirm_timeout_seconds: number;
}

interface ToolAuditEntry {
  timestamp: string; server_name: string; tool_name: string;
  arguments: Record<string, unknown>; status: string;
}

interface ConversationSummary {
  id: string; session_key: string; title: string; preview: string;
  updated_at: string; message_count: number;
}

interface ConversationDetail {
  id: string; session_key: string; created_at: string; updated_at: string;
  messages: { id: string; role: string; content: string; timestamp: string }[];
}

interface MemoryEntry {
  slug: string; name: string; description: string;
  type: "user" | "feedback" | "project" | "reference";
  body: string; filename: string;
}

interface MCPPreset {
  id: string; name: string; category: string; description: string;
  transport: string; command: string; args: string[];
  env: Record<string, string>;
}

interface RegistryServer {
  name: string; description: string; version: string;
  packages: { registry_type: string; identifier: string; version: string }[];
  remotes: { type: string; url: string }[];
}

interface ShellAllowResponse { commands: string[]; default: string[]; }
interface VoiceProfileResponse { status?: string; enrolled: boolean; samples?: number; }

interface VoicePreviewOptions {
  engine: "kokoro" | "piper" | "openai";
  voice: string; language?: "es" | "en"; text?: string;
  speed?: number; model?: string; instructions?: string; timeout_s?: number;
}
```

The full `GET /api/config` shape is large; the authoritative TS mirror is
`web/src/types/config.ts` (157 lines). The `voice` block alone has ~40 fields —
see `src/dax/web/routes/config.py:199-245` and `web/src/types/config.ts:21-60`.

### 4.4 `/ws/chat` protocol — COMPLETE

Source: `src/dax/web/routes/chat.py:71-135`, client:
`web/src/hooks/useChatSocket.ts`.

**Handshake:** cookie, or `?token=<session-token>`. On failure the server closes
with code **1008**. If the bus is not wired, code **1011**.

**Client → server:**

```jsonc
// Send a message
{ "content": "hola", "language": "auto", "session_id": "<uuid>" }
// language ∈ Language enum; unknown values fall back to "auto"
// empty/whitespace content is silently ignored
// session_id selects which persisted conversation to resume

// Respond to a tool-confirmation modal
{ "type": "tool_confirmation",
  "approval_id": "<hex>",
  "decision": "approve" | "once" | "save" | "deny" }
// Legacy clients may send { "approved": true|false } instead; the server maps
// true→"approve", false→"deny". New clients MUST send "decision".
```

**Server → client:**

```jsonc
// 1. Agent activity — drives the live "thinking" panel
{ "type": "agent_event", "event": { ... } }
// where event is one of:
{ "type": "thinking" }
{ "type": "tool_call",   "tool": "...", "server": "...", "args": { ... } }
{ "type": "tool_result", "tool": "...", "preview": "<first 300 chars>", "error": false }
{ "type": "done", "elapsed_s": 3.4 }

// 2. Final assistant turn
{ "type": "message", "role": "assistant", "content": "...", "timestamp": "<iso>",
  "channel": "web" }

// 3. Human-in-the-loop tool approval
{ "type": "tool_confirmation_request",
  "approval_id": "<hex>",
  "tool_name": "...", "server_name": "...",
  "arguments": { ... },
  "options": ["approve"] | ["once", "save"] | ...,
  "timeout_seconds": 60 }

// 4. Legacy (no "type" field) — { role: "assistant", content, timestamp }
//    Still handled by web/src/hooks/useChatSocket.ts. Port the handling.
```

Emission sites: `src/dax/orchestrator/agent.py:270` (`thinking`), `:349`
(`tool_call`), `:357` (`tool_result`), `:387` (`done`).
`src/dax/orchestrator/approval.py:93-100` builds the confirmation payload;
`:113-119` resolves it.

**Fail-safe semantics you must preserve in the UI:** the `ApprovalManager`
**denies on timeout** (`approval.py`, `except TimeoutError: return "deny"`) and
denies when no UI is connected. The desktop confirmation modal must therefore
show a visible countdown from `timeout_seconds` and must not silently swallow the
request.

**Outbound delivery path:** Dispatcher → WebChannel → `ws_manager.broadcast()`.
It is a **broadcast to all connected sockets**, not a per-socket reply. If both
the web SPA and the desktop app are open, both receive every frame. Filter client
side by `session_id` if this matters.

### 4.5 `/ws/logs` protocol — COMPLETE

Source: `src/dax/web/routes/logs.py`.

Same handshake and close codes as `/ws/chat`. **One-directional** — the server
pushes `LogEntry` JSON objects from a subscribed queue; the client sends nothing.
Client reference: `web/src/hooks/useLogStream.ts` (56 lines).

`LogEntry` shape is in `web/src/types/config.ts`. Levels observed in
`web/src/pages/Logs.tsx:10-18`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

### 4.6 `/ws/voice` protocol — PLANNED, NOT YET BUILT

**This is a backend prerequisite for Milestone 4.** It must be created at
`src/dax/web/routes/voice_ws.py` and registered in `src/dax/web/server.py:93-94`
under the `/ws` prefix alongside `chat.py` and `logs.py`, auth-gated identically.

The transport half already exists. `src/dax/core/voice_events.py` provides
`VoiceEventHub` with `subscribe()`, `unsubscribe(queue)`, `last_state`, and
`has_subscribers`. `src/dax/app.py` owns the hub as `self._voice_events`, exposed
as `app.state.voice_events`, and it outlives pipeline reloads.

**Server → client frames.** Every event serializes via `VoiceEvent.to_json()`:

```jsonc
{ "type": "state"|"level"|"transcript"|"speaker"|"error",
  "data": { ... },
  "timestamp": 1752871234.567 }
```

Per-type `data`:

```jsonc
// state — from VoiceEventHub.emit_state
{ "state": "idle"|"listening"|"processing"|"speaking"|"conversing",
  "conversation_id": "<id>"|null }
// PipelineState enum: src/dax/voice/pipeline.py:102-109
// Emitted on EVERY transition via the _state property setter (pipeline.py:271-276)

// level — from dax.voice.events.compute_level_frame
{ "source": "input"|"output",
  "rms": [0.0, 0.0, 0.0, 0.0],        // SUB_WINDOWS = 4
  "peak": 0.0,
  "spectrum": [0,0,0,0,0,0,0,0] }     // SPECTRUM_BANDS = 8
// All values normalized 0.0–1.0.
// input  = microphone  (pipeline.py:992, from _read_metered_chunk)
// output = TTS playback (pipeline.py:1001, from _emit_output_level via
//          AudioPlayer.play_blocks(on_block=...) at pipeline.py:711)

// transcript
{ "text": "...", "language": "es"|"en", "final": true }
// pipeline.py:576

// speaker
{ "verified": true|false, "score": 0.0|null }
// pipeline.py:554 (rejected), :558 (accepted)

// error
{ "message": "..." }
// pipeline.py:355
```

**Frame rate.** Capture chunk is 80 ms → ~12.5 level frames/s, each carrying 4 RMS
sub-windows → **~50 envelope points/s**. This is the number the waveform
interpolator (7.4) must smooth to 60 fps.

**Route requirements — write these into the implementation:**

1. Auth exactly like chat: `auth.authenticate_websocket(websocket)`, close 1008
   on failure.
2. `hub = getattr(websocket.app.state, "voice_events", None)`; close 1011 if None.
   Add a `voice_events_from_app` helper to `src/dax/web/dependencies.py` to match
   the existing `auth_from_app` / `bus_from_app` / `log_buffer_from_app` pattern.
3. `hub.bind_loop(asyncio.get_running_loop())` if not already bound.
4. **On connect, replay `hub.last_state`.** Without this a client connecting
   mid-conversation renders "idle" until the next transition. This is explicitly
   called out in the `VoiceEventHub.last_state` docstring.
5. If the voice extra is not installed or voice is disabled, still accept the
   connection and send a synthetic
   `{"type":"state","data":{"state":"idle","conversation_id":null}}` — the module
   is deliberately in `core` so this works without the optional extra.
6. Subscribe, loop on `await queue.get()`, `send_json(event.to_json())`.
7. `finally: hub.unsubscribe(queue)` — **mandatory**. `has_subscribers` gates all
   DSP work; a leaked subscriber means the pipeline computes FFTs forever.
8. Mirror the `except (WebSocketDisconnect, asyncio.CancelledError): pass`
   structure from `logs.py`.

**Client → server:** none in v1. Reserve the inbound direction for
`RemoteAudioSource` PCM (D4) in a later milestone.

**Test to add:** `tests/unit/test_voice_ws.py` — assert unauthenticated close is
1008, assert `last_state` replay on connect, assert `unsubscribe` runs on
disconnect (i.e. `hub.has_subscribers` is False afterwards).

---

## 5. Design system specification

> **5.0 supersedes everything below it.** Sections 5.1–5.9 describe the
> original macOS-token direction, which the user reviewed and rejected: it
> shipped, and it read as a web page. They are kept only as the record of what
> was tried and why it failed. **Build from 5.0.**

### 5.0 THE FIXED DESIGN — "Órbita" (authoritative, 2026-07-19)

Chosen by the user from four presented directions. The implementation is
`desktop/src/design/tokens.css`; that file is the source of truth for values
and this section is the source of truth for *why*.

#### Why the first attempt failed

Worth stating plainly, because the failure was encoded in tokens rather than
in any one screen — which is why it reproduced across every view:

```css
/* the rejected elevation scale */
--shadow-2: 0 2px 8px rgba(0,0,0,.07), 0 0 0 0.5px rgba(0,0,0,.07);
```

That second layer is a **border wearing a shadow's name**. Every panel in the
app was outlined. Combine it with radii of 4–10px, 13px body text and 28px
rows, and the result is a dense admin web UI. None of that was a taste
judgment that could be argued about — it was arithmetic.

#### The three rules

Any new component must satisfy all three. They are not stylistic preferences;
they are what separates this from the rejected build.

**1. Depth comes from shadow and elevation, never from a border.**
No elevation token carries an outline ring. Separation is expressed by, in
order of preference: space, then a background step (`--bg-elevated` /
`--bg-inset`), then elevation (`--shadow-1/2/3`). A `border` is a last resort
reserved for a *true structural divide* that space cannot express — currently
three in the entire app (markdown table head/body, `<hr>`, sidebar footer).
Shadows are two layers: a diffused drop that sells the float, plus a 1px inset
highlight on the top edge, which is how real glass catches light.

**2. Radii are large.**
Nothing interactive goes below `--radius-md` (10px). Panels and cards use
`--radius-xl` (18px). Small radii are the single strongest tell of a web
widget.

**3. Space is generous.**
Rows breathe (36px, not 28). Controls are a step larger than a web form would
use (buttons 28/34px, inputs 34px). Panels never touch the window edge — the
`--gutter` (12px) surrounds every floating pane. Body text is 14px/21px.

Corollary: `font-weight: 600` is banned. At these sizes heavy weights read as
web chrome; 500 is the maximum.

#### Colour

Dark is the default palette on `:root`; the opt-in class on `<html>` is
`.light` (note: inverted from the usual `.dark` convention — see
`lib/useTheme.ts`). Light is a genuine second design on a cool paper ground,
not an inversion.

The ground is a blue-biased near-black `#08090C`; panes sit at `#111319`.
Neutrals carry a deliberate cool hue bias — a pure grey reads as unconsidered.

**The accent is indigo `#6E8BFF`, and it is rationed.** It appears on:
the voice orb, one primary action per view, the send button, and the "on"
state of toggles and checkboxes. Nothing else. The rejected build used it for
selected nav rows, selected tabs, selected list rows, active header buttons,
and a solid accent tile on *every screen header* (`page.module.css`
`.pageMark`) — at which point it had stopped carrying any meaning at all.
Selection is now a raised surface (`--bg-elevated` + `--shadow-1`).

Semantic colours (`--success`, `--warning`, `--danger`) are a separate axis and
never stand in for the accent.

#### Typography

Two families, and the split between them *is* the personality:

- **Sans** (`system-ui` → Cantarell on GNOME, which is the native integration
  we want on the target platform) for anything a human said or reads.
- **Mono** for anything the machine asserts: session ids, tool names, log
  levels, metrics, latencies, counts, timestamps.

Uppercase machine labels get `--tracking-label` (0.08em); body text never gets
tracking. Numbers use `font-variant-numeric: tabular-nums` so columns align.

#### The voice orb

Direction D, "Órbita": a ring of 44 points circling a core, pushed outward and
brightened by amplitude. Implemented in `components/VoiceOrb.tsx`.

Canvas 2D, not WebGL — the workload is ~44 arcs per frame against Canvas's
several-thousand-draw budget; WebGL costs more on cold start and its driver
clocks the GPU harder, which is the wrong trade for a HUD that is idle most of
the time.

Two non-negotiable performance properties:
- Level frames arrive at ~12.5 Hz from `/ws/voice` and are **rAF-coalesced**.
  Pushing them into React state at socket rate re-renders the subtree 12×/s.
- The render loop **cancels itself** once the pipeline is idle and the spring
  has settled. A still orb must not hold a `requestAnimationFrame` loop open.
  The effect is keyed on `state` (so leaving idle restarts it) and deliberately
  *not* on `level`.

#### Structure: the command deck, not a sidebar

Approved 2026-07-19, replacing the classic sidebar + content-pane layout.

The app opens on a **command deck**: the orb at the centre, flanked by
at-a-glance panels, with a status bar above.

- **Top bar** — brand, `⌘K` hint, and what expires: pipeline state, session
  id, **session time remaining**, local time. That countdown was previously
  invisible and it is exactly what determines whether Dax remembers context.
- **Left column — your machine.** CPU, memory, disk, uptime; then voice status
  (turns, follow-up window, speaker verification, active wake word).
- **Centre — the orb.** Pipeline state, last transcript, and the command
  input. The orb is not buried in a settings tab: this is a voice assistant,
  so whether it is listening is the first thing you must be able to see.
- **Right column — the assistant.** MCP servers with connection LEDs and tool
  counts, the current turn's tool activity with latencies, and a live log tail.

Two principles govern it:

**The side panels are glanceable, not navigable.** Nothing there requires a
click to learn. If you have to open something to find out whether Dax is
operational, the structure has failed.

**Navigation is keyboard-first.** Chat, MCP, Marketplace, Logs and Settings
stop being permanent menu destinations and are summoned with `⌘K`. This is the
"hacker" quality the user asked for, and it is structural rather than
cosmetic — it is not terminal colours, it is that you do not navigate with the
mouse. The old sidebar spent 218 permanent pixels on links used once a day.

The live log is always present but quiet: an assistant that switches on lights
and touches your files must be auditable without going looking for it.

---

### 5.1 Grounding and honesty — HISTORICAL, superseded by 5.0

Apple does not publish a machine-readable macOS token set. The values below are
grounded where research supports them and are **calibrated approximations**
elsewhere. Each subsection says which.

**Verified from Apple/HIG research:**
- SF Pro Text is used at ≤19 pt; SF Pro Display at ≥20 pt (optical sizing).
- SF Pro Variable exposes `wght`, `wdth`, `opsz` axes; optical sizing is automatic.
- Spacing uses an **8 pt grid with 4 pt subdivisions**.
- Minimum interactive target: **44×44 pt** (Apple guidance since the original
  iPhone HIG).
- 17 pt body is the stated legibility floor.
- iOS Dynamic Type at default size spans Large Title 34 pt → Caption 2 11 pt.

**UNCERTAIN / calibrated:** macOS-specific corner radii, elevation shadow values,
and the exact desktop type ramp. macOS desktop text is denser than iOS Dynamic
Type — 13 pt is the standard macOS control/body size, not 17 pt. The ramp below
uses macOS desktop conventions, not the iOS scale.

### 5.2 Type

Font stack — SF when present (macOS), high-quality fallbacks elsewhere. On Fedora,
`Inter` or `Cantarell` will be what actually renders.

```css
--font-sans:
  ui-sans-serif, -apple-system, BlinkMacSystemFont,
  "SF Pro Text", "SF Pro Display",
  "Inter", "Cantarell", "Segoe UI", system-ui, sans-serif;

--font-mono:
  ui-monospace, "SF Mono", "JetBrains Mono", "Cascadia Code",
  "Liberation Mono", Menlo, monospace;
```

Ramp (macOS desktop conventions; sizes in px, 1 pt ≈ 1.333 px at 1× but we treat
them as CSS px directly):

| Token | Size | Line height | Weight | Tracking | Use |
| --- | --- | --- | --- | --- | --- |
| `--text-largetitle` | 26 | 32 | 700 | -0.02em | Screen hero, rare |
| `--text-title1` | 22 | 28 | 600 | -0.015em | Screen title |
| `--text-title2` | 17 | 22 | 600 | -0.01em | Section header |
| `--text-title3` | 15 | 20 | 600 | -0.005em | Panel header |
| `--text-body` | 13 | 18 | 400 | 0 | Default UI + chat body |
| `--text-callout` | 12 | 16 | 400 | 0 | Secondary body |
| `--text-subhead` | 11 | 14 | 500 | 0.01em | Labels |
| `--text-footnote` | 10 | 13 | 400 | 0.02em | Timestamps, hints |
| `--text-caption` | 9 | 12 | 500 | 0.04em | ALL-CAPS group headers |

Chat message body is an intentional exception: **14 px / 21 px** for reading
comfort over long assistant turns.

Enable optical sizing where SF is present:
`font-optical-sizing: auto; font-variant-numeric: tabular-nums;` — tabular figures
matter for the log viewer, token counts, and elapsed timers.

### 5.3 Spacing — 8 pt grid, 4 pt subdivisions (verified)

```css
--space-0:  0;
--space-1:  4px;
--space-2:  8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
```

Rhythm rules:
- Inside a control: `--space-2` horizontal, `--space-1` vertical.
- Between related controls in a form row: `--space-3`.
- Between form rows: `--space-4`.
- Between panels: `--space-6`.
- Screen padding: `--space-6` (24 px), matching the existing web UI's `p-6`.
- Sidebar item vertical padding: `--space-2`; item height 28 px, matching macOS
  source-list rows.

### 5.4 Corner radii (calibrated, UNCERTAIN)

```css
--radius-xs:  4px;   /* badges, tags, inline code */
--radius-sm:  6px;   /* buttons, inputs, small controls */
--radius-md:  8px;   /* sidebar row selection, list items */
--radius-lg: 10px;   /* panels, cards, popovers */
--radius-xl: 14px;   /* modals, sheets, chat bubbles */
--radius-2xl: 20px;  /* voice HUD */
--radius-window: 12px; /* window corner, transparency mode only */
```

Use **continuous-corner** shape where it matters. CSS `border-radius` is a
circular arc; Apple uses a squircle. For large radii (`--radius-xl` and up) the
difference is visible. Approximate with an SVG/CSS mask on the voice HUD and
modals only — do not chase it on buttons, the gain is not worth the complexity.

### 5.5 Elevation (calibrated, UNCERTAIN)

macOS uses low-contrast, large-radius, near-black shadows plus a 1 px hairline
border. Never use a colored or heavy shadow.

```css
/* Light */
--shadow-0: none;
--shadow-1: 0 1px 2px rgba(0,0,0,.05), 0 0 0 .5px rgba(0,0,0,.06);
--shadow-2: 0 2px 8px rgba(0,0,0,.07), 0 0 0 .5px rgba(0,0,0,.07);
--shadow-3: 0 8px 24px rgba(0,0,0,.10), 0 0 0 .5px rgba(0,0,0,.08);
--shadow-4: 0 16px 48px rgba(0,0,0,.16), 0 0 0 .5px rgba(0,0,0,.10);

/* Dark — shadows carry less; the hairline carries the separation */
--shadow-1: 0 1px 2px rgba(0,0,0,.30), 0 0 0 .5px rgba(255,255,255,.06);
--shadow-2: 0 2px 8px rgba(0,0,0,.36), 0 0 0 .5px rgba(255,255,255,.07);
--shadow-3: 0 8px 24px rgba(0,0,0,.44), 0 0 0 .5px rgba(255,255,255,.08);
--shadow-4: 0 16px 48px rgba(0,0,0,.55), 0 0 0 .5px rgba(255,255,255,.10);
```

The `0 0 0 .5px` layer is the **hairline**. On a 1× display .5px may not render;
fall back to `1px` with a lower alpha via
`@media (-webkit-min-device-pixel-ratio: 1.5)` inverted.

### 5.6 Semantic color tokens

Two themes. The web UI already uses `.dark`-class theming (per `CLAUDE.md`) —
keep that mechanism so any shared component works in both apps.

```css
:root {
  /* Surfaces — increasing elevation */
  --bg-window:        #ECECEE;   /* behind everything */
  --bg-sidebar:       rgba(246,246,248,.80);
  --bg-content:       #FFFFFF;
  --bg-panel:         #FFFFFF;
  --bg-elevated:      #FFFFFF;   /* popovers, modals */
  --bg-inset:         #F2F2F5;   /* code blocks, wells, log viewer */
  --bg-hover:         rgba(0,0,0,.045);
  --bg-active:        rgba(0,0,0,.075);
  --bg-selected:      rgba(0,122,255,.12);

  /* Text */
  --fg-primary:       rgba(0,0,0,.88);
  --fg-secondary:     rgba(0,0,0,.56);
  --fg-tertiary:      rgba(0,0,0,.36);
  --fg-quaternary:    rgba(0,0,0,.20);
  --fg-on-accent:     #FFFFFF;

  /* Separators */
  --separator:        rgba(0,0,0,.10);
  --separator-opaque: #D8D8DC;

  /* Accents — macOS system colors */
  --accent:           #007AFF;
  --accent-hover:     #0A6FE0;
  --accent-pressed:   #0761C4;
  --success:          #34C759;
  --warning:          #FF9F0A;
  --danger:           #FF3B30;
  --info:             #5AC8FA;
  --purple:           #AF52DE;

  /* Focus ring */
  --focus-ring:       rgba(0,122,255,.55);
  --focus-ring-width: 3px;
}

.dark {
  --bg-window:        #1C1C1E;
  --bg-sidebar:       rgba(38,38,41,.80);
  --bg-content:       #1E1E20;
  --bg-panel:         #252528;
  --bg-elevated:      #2C2C2F;
  --bg-inset:         #161618;
  --bg-hover:         rgba(255,255,255,.06);
  --bg-active:        rgba(255,255,255,.10);
  --bg-selected:      rgba(10,132,255,.22);

  --fg-primary:       rgba(255,255,255,.92);
  --fg-secondary:     rgba(255,255,255,.60);
  --fg-tertiary:      rgba(255,255,255,.38);
  --fg-quaternary:    rgba(255,255,255,.22);

  --separator:        rgba(255,255,255,.12);
  --separator-opaque: #38383C;

  --accent:           #0A84FF;
  --accent-hover:     #3D9BFF;
  --accent-pressed:   #0060DF;
  --success:          #30D158;
  --warning:          #FF9F0A;
  --danger:           #FF453A;
  --info:             #64D2FF;
  --purple:           #BF5AF2;

  --focus-ring:       rgba(10,132,255,.60);
}
```

The `#007AFF` / `#0A84FF` accent pair and the systemGreen/Orange/Red values are
Apple's published system colors for light/dark. The greys are calibrated, not
sampled — **UNCERTAIN**, adjust by eye against a real macOS screenshot if
fidelity matters.

### 5.7 Motion — spring easings

macOS animation is spring-based, not cubic-bezier. CSS cannot express a true
spring, so use bezier approximations for CSS and a real spring integrator for
JS-driven motion (the waveform, HUD entrance).

```css
/* Bezier approximations */
--ease-standard:  cubic-bezier(0.25, 0.10, 0.25, 1.00);
--ease-out-soft:  cubic-bezier(0.16, 1.00, 0.30, 1.00);  /* strong ease-out */
--ease-in-out:    cubic-bezier(0.65, 0.00, 0.35, 1.00);
--ease-spring:    cubic-bezier(0.34, 1.56, 0.64, 1.00);  /* slight overshoot */

--dur-instant: 80ms;
--dur-fast:   140ms;
--dur-normal: 220ms;
--dur-slow:   340ms;
--dur-hud:    420ms;
```

Assignment:
- Hover / press feedback → `--dur-instant`, `--ease-standard`
- Popover, dropdown, sheet in → `--dur-normal`, `--ease-out-soft`
- Modal in → `--dur-slow`, `--ease-out-soft`; out → `--dur-fast`, `--ease-standard`
- Voice HUD in → `--dur-hud`, `--ease-spring` (overshoot is correct here)
- Sidebar selection → `--dur-fast`, `--ease-standard`

For JS springs use the standard damped-harmonic parameterization. Suggested
presets: `{ stiffness: 210, damping: 20 }` (snappy UI), `{ stiffness: 120,
damping: 14 }` (HUD, slight bounce).

**Mandatory:** honor `@media (prefers-reduced-motion: reduce)` — collapse all
durations to `1ms` and disable the waveform's spring interpolation (fall back to
direct value assignment).

### 5.8 Focus rings

macOS uses a soft, wide, accent-colored halo, not a hard outline.

```css
:focus-visible {
  outline: none;
  box-shadow: 0 0 0 var(--focus-ring-width) var(--focus-ring);
  border-radius: inherit;
}
```

Only `:focus-visible`, never `:focus` — mouse clicks must not produce rings.

### 5.9 Sidebar treatment

The signature element. Specification:

- Width 240 px expanded, 56 px collapsed (the existing web UI uses `w-60` / `w-14`
  — `web/src/components/AppShell.tsx:52`).
- Background `--bg-sidebar` (semi-opaque). **No blur on Linux** — see 3.6.
- Right edge: 1 px `--separator`, not a shadow.
- Rows: 28 px tall, `--radius-md`, `--space-2` inset from the sidebar edges.
- Selected row: `--bg-selected` fill, `--fg-primary` text, accent-tinted icon.
- Hover: `--bg-hover`, no border change.
- Group headers: `--text-caption`, uppercase, `--fg-tertiary`, `--space-4` top
  margin.
- Icons: 16 px, `--fg-secondary` unselected, `--accent` selected.
- Collapse transition: `--dur-normal`, `--ease-out-soft`, animating `width` only.

### 5.10 Component inventory to build

Minimum primitive set before screen work starts:

`Button` (primary/secondary/ghost/destructive × sm/md), `IconButton`, `TextInput`,
`TextArea`, `Select`, `Toggle`, `Slider`, `Checkbox`, `Radio`, `Badge`, `Panel` +
`PanelHeader`, `Field` (label + description + control + error), `Modal`, `Sheet`,
`Popover`, `Tooltip`, `Toast`, `Tabs`, `SegmentedControl`, `List` + `ListRow`,
`Separator`, `Spinner`, `EmptyState`, `Markdown`, `CodeBlock`.

The web UI's `web/src/components/ui.tsx` (236 lines) has `Panel`, `PanelHeader`,
`Field`, `TextInput`, `TextArea`, `Select`, `Badge`, `Toggle`, `Modal`,
`useToast`. **Read it for the API shape, then reimplement** — do not import
HeroUI into the desktop app. HeroUI v3 carries its own visual language and
fighting it to look like macOS costs more than writing 25 small components.

---

## 6. Screen-by-screen implementation plan

### 6.0 SETTINGS INFORMATION ARCHITECTURE (authoritative, 2026-07-19)

The complete, verified surface is **84 configuration fields across 10 pydantic
sections**, plus two dynamic collections (MCP servers, memory files) and two
list-valued policies (tool policy, shell allowlist). Verified by enumerating
`DaxConfig.model_fields`, not estimated:

| Section | Fields |
|---|---|
| `voice` | **42** |
| `llm` | 10 (incl. 6 nested provider blocks) |
| `security` | 6 |
| `whatsapp` | 6 |
| `web` | 5 |
| `telegram` | 4 |
| `tools` | 3 |
| `storage` | 2 |
| `mcp` | 1 (`servers`, a dynamic map) |
| root scalars | 5 (`name`, `language_default`, `log_level`, `memory_path`, `system_prompt`) |

#### What was wrong before

The shipped tabs were `General · LLM · Voice · Tools · MCP · Memory ·
Telegram · WhatsApp · Server` — a **one-to-one mirror of the backend's config
schema**. That is the classic settings mistake: it organises by how the system
is built rather than by what the person is trying to do. Nobody thinks "I want
to change my web config"; they think "I want Dax to hear me better", which
today is split across `voice.vad_threshold`, `voice.wake_word_threshold`,
`voice.denoise` and `voice.silence_duration_ms` with no grouping that says so.

It also put all 42 voice fields on one flat tab, which is unusable, and gave
`storage` (2 fields, read-only in practice) the same visual weight as `voice`.

#### The three governing principles

Drawn from the research (sources in section 14):

**Search-first.** With 84 fields, browsing is the fallback and search is the
primary interaction — this is the VS Code lesson. A persistent search field
filters every field across every section by label, description, and underlying
config key, so `session_ttl_minutes` finds it even if the user only remembers
the technical name. Searching must show which section a result lives in.

**Progressive disclosure, capped at two levels.** Section → group → field.
Never deeper; the research is explicit that more than about three levels
inverts the benefit. Each group has an **Advanced** disclosure holding the
fields that are correct by default and dangerous to fiddle with
(`stt_compute_type`, `stt_device`, `stt_beam_size`, `vad_threshold`,
`speaker_threshold`, `wake_word_threshold`, timeouts). Advanced is collapsed by
default and its state is not remembered — reopening settings returns to the
calm view.

**Task-named, not schema-named.** Every section and group is named for the
user's intent. The underlying config key is still shown, in mono, as secondary
metadata — this is a single-user self-hosted tool and its owner is technical,
so hiding the key would be condescending. But the key is never the label.

#### The structure

Seven sections, replacing nine:

**1. Voz** — the largest surface, so it carries the most internal structure.
- *Cómo te escucha* — wake word + model, mic sensitivity, denoise, endpointing
- *Cómo conversa* — follow-up window, question window, session TTL, barge-in,
  earcon, spoken confirmations, require-wake-each-turn
- *Cómo habla* — TTS engine, per-language voice, speed, instructions
- *Cómo transcribe* — STT backend/model/language, hosted-vs-local fallback
- *Quién puede hablarle* — speaker verification, enrollment, threshold
- Live status with the orb sits at the top of this section, not in a tab

**2. Inteligencia** — `llm`. Active provider, model, fallback chain, and the
tool budget (`max_tools`, `max_tool_iterations`). Each provider block is a
disclosure, since only the active one usually matters.

**3. Capacidades** — what Dax is allowed to do. Merges `mcp.servers`, the tool
policy (allow/ask/deny), and the shell allowlist. These are one mental model —
"what can it touch" — and splitting them across MCP and Tools tabs was wrong.

**4. Memoria** — `memory_path`, the memory file CRUD, and `system_prompt`.
The prompt belongs with memory: both are "what Dax knows about you".

**5. Canales** — Telegram and WhatsApp. Two connectors, same shape, so they
are two groups in one section rather than two tabs.

**6. Acceso** — `security` + `web`. Password, session lifetime, cookie flags,
bind host/port, LAN exposure, CORS. One question: who can reach this and how.

**7. Sistema** — `storage` paths, `log_level`, `name`, `language_default`,
plus desktop-only preferences (theme, backend URL, launch at login).

#### Rules for field rendering

- Every field shows a **description under the label**, not in a tooltip. The
  `Tooltip` primitive exists but is unused, and should stay unused here: a
  tooltip hides exactly the text that makes a setting comprehensible.
- Destructive or restart-requiring fields are marked inline. `web.host`,
  `web.port` and Telegram need a restart; LLM and tool policy apply live.
  Saying so at the field prevents the "I changed it and nothing happened"
  failure.
- Secret fields (`password_hash`, `session_secret`, API keys, MCP headers and
  env values) are masked, and a PATCH that echoes the mask back must be
  understood by the server as "unchanged" — this is already the backend's
  contract (see CLAUDE.md) and the UI must not defeat it.
- Save is explicit per group, not per keystroke, and the group shows a dirty
  state. Auto-save on a field like `bind host` is hostile.

#### Coverage requirement

The user's requirement is **absolutely every config**. A field that exists in
`DaxConfig` and has no control anywhere in Settings is a bug. The verification
gate for this section is a test that enumerates `DaxConfig.model_fields`
recursively and asserts each leaf key appears in the UI's field registry, so
coverage cannot silently regress when the backend gains a field.

---

### 6.1 Inventory of the existing web UI (verified line counts)

| File | Lines | Role |
| --- | --- | --- |
| `web/src/pages/Chat.tsx` | 795 | Chat |
| `web/src/pages/settings/McpTab.tsx` | 714 | MCP server CRUD |
| `web/src/pages/settings/MemoryTab.tsx` | 411 | Memory CRUD |
| `web/src/pages/settings/VoiceTab.tsx` | 381 | Voice config |
| `web/src/api/client.ts` | 380 | API client |
| `web/src/pages/settings/LLMTab.tsx` | 365 | LLM providers |
| `web/src/pages/McpMarketplace.tsx` | 314 | Preset/registry browse |
| `web/src/pages/settings/ToolsTab.tsx` | 263 | Tool policy + security |
| `web/src/pages/settings/GeneralTab.tsx` | 251 | Identity, prompt, export |
| `web/src/components/ui.tsx` | 236 | Primitives |
| `web/src/pages/settings/VoiceEnrollment.tsx` | 192 | Voice ID enrollment |
| `web/src/hooks/useChatSocket.ts` | 183 | Chat WS |
| `web/src/pages/Dashboard.tsx` | 179 | Status overview |
| `web/src/pages/Shell.tsx` | 178 | Shell allowlist |
| `web/src/types/config.ts` | 157 | Config types |
| `web/src/components/AppShell.tsx` | 133 | Nav shell |
| `web/src/pages/Login.tsx` | 132 | Login + first-run setup |
| `web/src/pages/settings/VoiceGallery.tsx` | 118 | TTS voice preview |
| `web/src/pages/settings/TelegramTab.tsx` | 113 | Telegram |
| `web/src/pages/Logs.tsx` | 105 | Log viewer |
| `web/src/pages/settings/WhatsAppTab.tsx` | 103 | WhatsApp |
| `web/src/pages/settings/ServerTab.tsx` | 100 | Host/port/CORS |
| `web/src/pages/Mcp.tsx` | 98 | MCP page + export panel |
| `web/src/pages/settings/SettingsPage.tsx` | 60 | Settings tab router |
| `web/src/hooks/useLogStream.ts` | 56 | Logs WS |
| `web/src/hooks/useConfig.ts` | 55 | Config/status hooks |
| `web/src/hooks/useTheme.ts` | 52 | Theme |
| `web/src/lib/audio.ts` | 48 | Recording helpers |
| others | — | Markdown, ThemeToggle, AuthGate, ToastProvider, cn, tests |
| **Total** | **6,411** | |

Navigation (`web/src/components/AppShell.tsx:23-30`): Chat `/`, Dashboard
`/dashboard`, MCP `/mcp`, Commands `/shell`, Logs `/logs`, Settings `/settings`.
Settings tabs: General, LLM, Voice, Tools, MCP, Memory, Telegram, WhatsApp,
Server.

### 6.2 Parity checklist

#### Login (`Login.tsx`, 132 lines)

- [ ] Single screen handles both first-run setup and normal login, keyed on
      `configured` from `GET /api/auth/status`
- [ ] Setup mode: password + confirm; client-side min-8-chars; mismatch check;
      calls `POST /api/auth/setup` and signs in
- [ ] Login mode: `POST /api/auth/login`
- [ ] Show/hide password toggle
- [ ] Distinct error copy for setup vs login failure
- [ ] **Desktop addition:** backend URL field (which host to connect to) and a
      "Start local backend" affordance when in sidecar mode
- [ ] **Desktop addition:** store the token in the OS keyring, not `localStorage`

#### Chat (`Chat.tsx`, 795 lines) — the most complex screen

- [ ] Conversation sidebar: list from `GET /api/conversations`, search filter,
      relative timestamps (`formatRelative`, `Chat.tsx:38`), delete with a
      pending state
- [ ] Session management: `newSessionId()` / `getStoredSessionId()`
      (`Chat.tsx:32-36`); new-chat creates a fresh id; selecting a conversation
      loads `GET /api/conversations/{id}` into `initialMessages`
- [ ] Message list with user/assistant bubbles (`MessageBubble`, `Chat.tsx:154`)
- [ ] Markdown rendering with GFM + syntax highlighting (`remark-gfm`,
      `rehype-highlight`, `highlight.js` per `web/package.json`)
- [ ] Live thinking trail: `ThinkingTrail` (`Chat.tsx:126`) rendering `StepLine`
      (`:63`) per agent event, updating in real time from `liveEvents`
- [ ] Collapsible post-hoc thought log: `ThoughtToggle` (`Chat.tsx:93`) with
      elapsed time
- [ ] Activity panel (`ActivityPanel`, `Chat.tsx:182`) — toggled side panel
- [ ] Model selector (`ModelSelector`, `Chat.tsx:263`) — provider + model, loads
      from `GET /api/llm/models`
- [ ] Tool confirmation modal — `tool_confirmation_request` → modal with the
      `options` array as buttons, a **visible countdown** from `timeout_seconds`,
      replying `{ type: "tool_confirmation", approval_id, decision }`
- [ ] Copy-link / share affordance (`linkCopied`, `Chat.tsx:372`)
- [ ] Auto-reconnect with 2 s backoff (`useChatSocket.ts:69-72`)
- [ ] Connection status indicator (connecting / open / closed)
- [ ] **Desktop addition:** voice HUD entry point in the composer

#### Dashboard (`Dashboard.tsx`, 179 lines)

- [ ] Four stat cards: Status, LLM provider, MCP servers, Tools (sum of
      `tool_count`) — from `GET /api/status` + `GET /api/mcp/status`
- [ ] MCP server list with connected/disconnected state
- [ ] Recent tool audit (`GET /api/tools/audit?limit=20`)
- [ ] Graceful empty states
- [ ] **Desktop addition:** backend process card — mode, PID, uptime, health,
      start/stop/restart

#### Logs (`Logs.tsx`, 105 lines)

- [ ] Live stream over `/ws/logs`
- [ ] Level filter: ALL / DEBUG / INFO / WARNING / ERROR
- [ ] Per-level color coding (`Logs.tsx:10-18`)
- [ ] Follow-tail toggle with auto-scroll
- [ ] Clear buffer
- [ ] Live/disconnected badge + line count
- [ ] **Desktop addition:** merge sidecar stdout/stderr (from the Rust
      `backend://stdout` events) into the same view, visually distinguished
- [ ] **Performance:** virtualize the list. The web version renders every line;
      at 50k lines that is a memory problem. Cap the ring buffer (e.g. 10k) and
      virtualize.

#### Shell / Commands (`Shell.tsx`, 178 lines)

- [ ] Load allowlist + defaults (`GET /api/config/system/shell-allow`)
- [ ] Add commands, splitting input on whitespace/commas, dedup
- [ ] Remove commands
- [ ] Dirty tracking, explicit save (`PUT`), reset-to-defaults
- [ ] Explain the security model: listed commands run without asking; anything
      else prompts in chat where the user can approve-and-save

#### MCP (`Mcp.tsx` 98 + `McpTab.tsx` 714)

- [ ] Server table: name, transport, connected, enabled, tool count, tool list
- [ ] Add server modal: name, transport (stdio/http), command, space-separated
      args, URL, HTTP headers, env vars — with the `parseEnv` / `parseHeaders` /
      `envToText` / `headersToText` round-trip helpers (`McpTab.tsx:37-73`)
- [ ] Edit, reconnect, delete per row
- [ ] Per-row flags for Codex / Claude export
- [ ] OAuth: start → open the authorization URL **in the system browser** → poll
      `GET /api/mcp/{name}/auth/status` → show authenticated/expired → logout
- [ ] Export panel: copy Codex TOML / Claude JSON to clipboard, warn when
      `server_count` is 0 (`Mcp.tsx:30-40`)
- [ ] Header and env values are **encrypted secrets** — respect the masking
      convention (4.2)

#### MCP Marketplace (`McpMarketplace.tsx`, 314 lines)

- [ ] Curated presets (`GET /api/mcp/presets`), grouped by category
- [ ] Registry search (`GET /api/mcp/registry/search?q=&limit=30`), handling the
      `error` field
- [ ] Install flow prefilling the add-server form from a preset
- [ ] Show required env vars per preset

#### Settings — General (`GeneralTab.tsx`, 251 lines)

- [ ] Assistant name, default language, log level
- [ ] System prompt editor with reset-to-default
      (`POST /api/config/general/system-prompt/reset`) and a `system_prompt_custom`
      indicator
- [ ] MCP export-to-external-clients panel (duplicated with `Mcp.tsx` — consider
      unifying in the desktop build)

#### Settings — LLM (`LLMTab.tsx`, 365 lines)

- [ ] Default provider + fallback order (ordered list)
- [ ] `max_tools` (default 45) — **document the latency tradeoff in the UI**:
      too low and tools never reach the model; too high and prompts balloon
      (~85 s responses at 120). See `CLAUDE.md`
- [ ] Per-provider blocks: Ollama (model, base URL, timeout, model discovery via
      `GET /api/ollama/models`), Anthropic, OpenAI, Gemini, DeepSeek, Codex
      (binary path, model)
- [ ] API key fields respecting the mask convention
- [ ] Model discovery via `GET /api/llm/models?provider=`

#### Settings — Voice (`VoiceTab.tsx`, 381 lines)

~40 fields. Group them:
- [ ] Enable toggle; wake word model + threshold
- [ ] STT backend (local / openai); local: model, beam size, device, compute
      type; openai: model, API key, timeout, prompt vocabulary, local fallback
- [ ] STT language
- [ ] TTS engine (kokoro / piper / openai) with per-engine voice + speed +
      instructions + timeout + fallback
- [ ] VAD threshold, silence duration, adaptive endpointing, denoise, barge-in,
      earcon
- [ ] Conversation timeout, follow-up activation ms, thinking pause ms, response
      timeout
- [ ] `voice_confirm`, `require_wake_word_each_turn`
- [ ] Speaker verification toggle + threshold

#### Settings — Voice Enrollment (`VoiceEnrollment.tsx`, 192 lines)

- [ ] Record 3–5 samples in-app (`_MIN_SAMPLES` / `_MAX_SAMPLES` enforced server
      side)
- [ ] Upload as multipart to `POST /api/voice/enroll`
- [ ] Show enrolled state from `GET /api/voice/profile`
- [ ] Delete profile
- [ ] Handle 422 (unusable speech / wrong count) and 503 (Voice ID model
      unavailable) distinctly
- [ ] **Desktop advantage:** use native mic capture with a real level meter
      during recording instead of the browser's `MediaRecorder`

#### Settings — Voice Gallery (`VoiceGallery.tsx`, 118 lines)

- [ ] Browse available voices per engine
- [ ] Preview via `POST /api/voice/preview` → WAV blob → play
- [ ] Handle 503 when the engine is unavailable

#### Settings — Tools (`ToolsTab.tsx`, 263 lines)

- [ ] Tool policy: default decision, ask / allow / deny pattern lists (one per
      line), confirmation timeout
- [ ] Security: require login, session lifetime hours, secure cookie
- [ ] Change password (current + new + confirm, min 8)

#### Settings — Memory (`MemoryTab.tsx`, 411 lines)

- [ ] List, search, create, edit, delete memory entries
- [ ] Type selector: user / feedback / project / reference
- [ ] Editor: title, description, body (markdown)
- [ ] Split list/detail layout

#### Settings — Telegram (`TelegramTab.tsx`, 113 lines)

- [ ] Enabled toggle, bot token (masked), allowed user IDs, respond-with-audio
- [ ] **Show a "requires restart" notice** — Telegram changes do not apply live

#### Settings — WhatsApp (`WhatsAppTab.tsx`, 103 lines)

- [ ] Enabled toggle, Evolution API URL, instance, API key (masked),
      respond-with-audio

#### Settings — Server (`ServerTab.tsx`, 100 lines)

- [ ] Host, port, expose-LAN toggle, CORS origins
- [ ] **Show a "requires restart" notice** — host/port do not apply live
- [ ] **Desktop addition:** when in sidecar mode, offer to restart the backend
      immediately after saving

### 6.3 Frontend framework recommendation

**Recommendation: React 19.**

Evaluated against Solid and Svelte.

| Criterion | React 19 | Solid | Svelte 5 |
| --- | --- | --- | --- |
| Port cost from `web/` (6,411 lines) | Near-zero — hooks, JSX, and component structure carry over | Full rewrite of every hook and effect | Full rewrite |
| Runtime bundle | ~45 KB gzip (react + react-dom) | ~7 KB | ~2 KB |
| Runtime perf | Adequate; VDOM diffing | Faster fine-grained updates | Faster fine-grained updates |
| Ecosystem for our needs | `react-markdown`, `rehype-highlight`, `remark-gfm` already in use and proven against this backend | Equivalents exist but are less mature | Equivalents exist |
| Team familiarity | The repo is already React | New | New |

**Reasoning.** The bundle-size argument does not apply here. This is a desktop app
loading from local disk, not a web page over a network — 40 KB of extra JS costs
approximately nothing on startup and nothing on memory relative to WebKitGTK's own
footprint. The runtime-performance argument is real but narrow: the only genuinely
hot path is the voice waveform, and that is a Canvas render loop outside the
framework's reconciler entirely (7.4). Everything else is forms and lists.

Meanwhile the port cost is the dominant term. `useChatSocket.ts` (183 lines) is
subtle — pending-event refs, live-event state, elapsed tracking, reconnect
backoff, legacy-frame fallback — and it is *known to work* against this backend.
Rewriting it in a different reactivity model to save 40 KB is a bad trade and
risks reintroducing bugs the web version already fixed.

**Specifics:**
- React 19.2+ (matching `web/package.json`)
- Vite 8 + `@vitejs/plugin-react-swc` (matching `web/`)
- **No HeroUI.** Build the design system from scratch (5.10). This is the single
  biggest divergence from `web/` and it is intentional — D3 requires a different
  visual language.
- **Tailwind v4 is optional.** Consider plain CSS Modules + the token file
  instead. Tailwind's value is rapid iteration on a utility vocabulary; for a
  hand-tuned design system with ~25 primitives, CSS Modules give better control
  over the fine details (hairlines, .5px borders, optical sizing) with less
  fighting. **This is a genuine judgment call — either is defensible.** If the
  implementing agent prefers Tailwind v4 for consistency with `web/`, that is
  acceptable; do not litigate it for more than 10 minutes.
- State: React built-ins + a small store (Zustand or `useSyncExternalStore`) for
  the three WebSocket connections and backend status. **Do not add Redux.**
- Routing: `react-router` v7 (matching `web/`) or a hash router. Tauri serves from
  a custom protocol; verify history-mode routing works before committing —
  **UNCERTAIN**, hash routing is the safe fallback.

### 6.4 Screens unique to the desktop app

- **Voice HUD** — section 7
- **Backend control** — mode (sidecar/remote), URL, start/stop/restart, live
  health, sidecar log tail. Lives in Settings as a new "Desktop" tab, plus a card
  on Dashboard.
- **Desktop preferences** — global hotkey binding, autostart, tray behavior,
  notification preferences, theme (light/dark/system), start-minimized.

---

## 7. Voice UI specification

### 7.1 Data available

From `/ws/voice` (4.6):

- **State** — `idle` / `listening` / `processing` / `speaking` / `conversing`
  (`src/dax/voice/pipeline.py:102-109`), emitted on every transition via the
  `_state` property setter (`pipeline.py:271-276`).
- **Level** — ~12.5 frames/s, each with 4 RMS sub-windows, 1 peak, 8 spectrum
  bands, all 0.0–1.0, tagged `input` (mic) or `output` (TTS playback).
- **Transcript** — final text + detected language.
- **Speaker** — verified boolean + score.
- **Error** — message string.

### 7.2 Voice HUD window

A **separate Tauri window**, not a modal in the main window. Rationale: it must be
usable when the main window is hidden or the app is in the tray.

Properties:
- Label `voice-hud`
- `decorations: false`, `transparent: true`, `alwaysOnTop: true`, `skipTaskbar: true`,
  `resizable: false`
- ~380 × 140 px, positioned bottom-center of the active display with a 48 px inset
- Shown by: global hotkey, tray menu item, wake-word detection (a `state`
  transition out of `idle`), or the composer button
- Auto-hides on return to `idle` after a ~1.5 s grace period
- **Wayland caveat (3.6):** CSS shadows will clip at the window edge. Use
  `transparent: true` plus an internal CSS margin equal to the shadow radius so
  the shadow lives inside the window bounds.
- **UNCERTAIN:** precise window positioning on Wayland is compositor-controlled
  and `set_position` may be ignored. Validate early; fall back to letting the
  compositor place it.

### 7.3 HUD visual states

| State | Waveform | Text | Accent |
| --- | --- | --- | --- |
| `idle` | Flat line, no animation, **RAF loop stopped** | — | `--fg-tertiary` |
| `listening` | Live mic envelope, symmetric bars | "Listening…" | `--accent` |
| `processing` | Waveform freezes and dims; an indeterminate shimmer traverses it | "Thinking…" | `--fg-secondary` |
| `speaking` | Live TTS output envelope | Streaming transcript | `--purple` |
| `conversing` | Live mic envelope, dimmer chrome | "Go ahead…" | `--accent` |
| error | Waveform collapses; message shown | Error text | `--danger` |

Transcript renders below the waveform, fading in per phrase. Speaker verification
failure shows a small "Voice not recognized" chip.

### 7.4 Waveform rendering — recommendation

**Recommendation: Canvas 2D with `requestAnimationFrame`, plus a spring
interpolator, plus a hard stop when idle.**

Options considered:

| Approach | Verdict |
| --- | --- |
| **CSS** (animated bar heights via transforms) | Rejected. ~48 elements each with per-frame style writes causes layout/paint churn; getting spring interpolation right per-element is worse than one canvas draw. Its one advantage — compositor-driven animation — does not apply because our values change every frame from data. |
| **WebGL** | Rejected as over-engineering. Research indicates WebGL wins above ~3,000 draws per frame; we need ~48 rounded rects. WebGL also has a slower cold start (~40 ms vs ~15 ms for Canvas 2D) and, critically for D5, its driver can clock the GPU aggressively and draw more power than Canvas — the opposite of what a mostly-idle HUD needs. |
| **Canvas 2D** | **Chosen.** Comfortably handles 1,000–3,000 simple draws per frame at 60 fps on a mid-range laptop. Our workload is ~50× under that. One draw call path, trivial to stop and start, no GPU context to keep alive. |

**Architecture:**

```
/ws/voice level frame (~12.5 Hz, 4 RMS points each)
        │
        ▼
  ring buffer of envelope samples (~50 points/s pushed)
        │
        ▼
  spring interpolator, stepped once per RAF frame (60 Hz)
        │
        ▼
  Canvas 2D draw: N symmetric rounded bars
```

**Implementation requirements:**

1. **Ring buffer.** Fixed-size `Float32Array` (e.g. 256 entries), write index
   wraps. Zero allocation per frame. Never `push`/`shift` an array.
2. **Interpolation.** Each of the N displayed bars holds a spring state
   `{ value, velocity }`. Per RAF frame, step the spring toward the target
   sampled from the ring buffer. Parameters ≈ `{ stiffness: 180, damping: 18 }`
   — tune by eye. This is what converts 12.5 Hz data into 60 fps motion; do not
   use linear lerp, it looks mechanical.
3. **Idle stop — this is the D5 requirement.** When state is `idle` **and** every
   spring has settled (all `|velocity| < ε` and `|value| < ε`), `cancelAnimationFrame`
   and do not reschedule. Restart the loop only when a `level` frame or a
   non-idle `state` frame arrives. A running RAF loop drawing a flat line is
   still 60 wakeups/second and will show up as measurable CPU — **it must
   actually stop.**
4. **DPR handling.** Size the backing store to `clientWidth * devicePixelRatio`,
   scale the context once. Recompute only on resize, never per frame.
5. **Draw cost.** N ≈ 48 bars. Precompute x positions and bar width on resize.
   Per frame: one `clearRect`, then N `roundRect` + `fill`. Batch same-colored
   bars into a single path where possible.
6. **No React re-renders in the loop.** The canvas element is mounted once by
   React; the RAF loop and the WebSocket handler write to refs and touch the
   canvas directly. React state changes only on *state* transitions (5 per
   conversation), never on level frames.
7. **Reduced motion.** Under `prefers-reduced-motion: reduce`, skip the spring
   and assign values directly; optionally replace the waveform with a static
   level meter.
8. **Backpressure.** The hub is lossy by design (`_QUEUE_MAXSIZE = 64`,
   `src/dax/core/voice_events.py:38`). Dropped frames are expected and invisible
   after interpolation. Do not add client-side buffering to "recover" them.

**Optional spectrum mode.** The 8-band spectrum enables a bar-EQ visualization as
an alternative to the envelope. Same renderer, different input. Build the envelope
first; spectrum is a nice-to-have.

### 7.5 Voice controls surface

- Global hotkey: push-to-talk (hold) and summon (toggle). Bound in Rust
  (`hotkeys.rs`), delivered as `hotkey://*` events.
- Tray menu: "Talk to Dax", "Voice on/off" (→ `POST /api/voice/toggle`), "Open Dax",
  "Quit".
- Main-window composer: a mic button that opens the HUD.
- Voice-channel tool confirmations are routed to the **spoken** approver when one
  is registered (`src/dax/orchestrator/approval.py:66-78`), *not* to the web
  modal. The HUD should display what is being asked but must not assume it owns
  the decision.

### 7.6 Pluggable audio source (D4) — later milestone

Backend change, out of scope until Milestone 7:

```
dax.voice.sources.AudioSource        (Protocol)
  ├─ LocalAudioSource   — wraps the existing AudioCapture (sounddevice)
  └─ RemoteAudioSource  — asyncio queue fed by inbound PCM on /ws/voice
```

`VoicePipeline.__init__` (`src/dax/voice/pipeline.py:130-150`) already constructs
`AudioCapture` directly at `:167`. The refactor: accept an `AudioSource` and
default to `LocalAudioSource`. `_read_metered_chunk` (`:982`) becomes source
agnostic.

`RemoteAudioSource` requires the desktop to capture PCM (16 kHz mono int16, 80 ms
chunks to match `CHUNK_SIZE`) and stream it as binary WebSocket frames on the
inbound direction of `/ws/voice`. Capture in Rust via `cpal` (avoids webview
`getUserMedia` permission friction and gives lower latency) or in TS via
`AudioWorklet`. **Decide at Milestone 7, not before.**

---

## 8. Non-goals

Explicitly out of scope, recorded so they are not accidentally attempted:

- Rewriting STT / TTS / wake-word in Rust (D4)
- Mobile targets (Tauri v2 supports them; we do not want them)
- Multi-user support — Dax is single-user by design
- Replacing the web SPA — both clients coexist
- Offline mode — the backend is required
- An in-app terminal — the Shell screen manages an *allowlist*, it does not run
  commands

---

## 9. Risk register

| # | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| R1 | ~~Cookie auth fails across the webview origin boundary~~ **CLOSED at M0** | — | Resolved: login/setup now return the token, `is_authenticated` validates every offered credential, WS accepts `Authorization: Bearer`. Verified over real HTTP against live uvicorn. |
| R5 | CORS rejects the webview origin | **Blocks everything** | `tauri://localhost` and `http://tauri.localhost` MUST be in `web.cors_origins`, or every request fails with 400 "Disallowed CORS origin". Applied to this machine's config 2026-07-18; a fresh install must repeat it. |
| R2 | Python sidecar packaging is impractical (size/native deps) | Loses "one launch" | Ship remote-mode default (3.7 option C). Already the plan. |
| R3 | Wayland ignores HUD positioning / clips shadows | Cosmetic degradation | 3.6 workarounds; accept compositor placement |
| R4 | WebKitGTK memory exceeds the 90–140 MB budget | Violates D5 | Measure at every milestone (section 10). Virtualize long lists. If exceeded, the fallback is reducing in-memory buffers, not switching stacks. |
| R5 | Rebuilding ~25 primitives takes longer than estimated | Schedule | Milestone 1 builds only what Milestone 2 needs; grow the set per screen |
| R6 | HeroUI-specific behaviors in `web/` have no obvious equivalent | Parity gaps | Read `web/src/components/ui.tsx` for the API contract before reimplementing |
| R7 | Broadcast chat frames reach both clients simultaneously | Confusing duplicates | Filter by `session_id` client-side (4.4) |
| R8 | `max_tools` / latency behavior surprises users | UX | Document the tradeoff in the LLM settings UI (6.2) |

---

## 10. Phased milestones

Each milestone is independently shippable and has an explicit verification gate.
**Do not proceed past a gate that fails.**

### M0 — Spike: prove the risky assumptions (1–2 days)

Throwaway code. The point is to answer questions, not to build.

- [ ] `dnf install librsvg2-devel libxdo-devel`
- [ ] `cargo create-tauri-app` scaffold in a scratch dir; confirm it builds and
      runs on Fedora 44 / Wayland
- [ ] **R1:** from the Tauri webview, `fetch` `POST /api/auth/login` against a
      running backend and then `GET /api/config`. Does the cookie replay?
      Record the answer in this document.
- [ ] **R1 fallback:** confirm `/ws/chat?token=<t>` authenticates (the code path
      exists at `src/dax/web/auth.py:150`)
- [ ] **R3:** create a second transparent, undecorated, always-on-top window.
      Does positioning work? Do shadows clip?
- [ ] **R4:** measure baseline RSS of an empty Tauri window on this machine
- [ ] Confirm `react-router` history mode works from the Tauri custom protocol,
      or fall back to hash routing

**Gate:** every question above has a written answer in section 12 of this file.

#### M0 RESULTS — completed 2026-07-18. Gate: **PASSED.**

Environment as built: Tauri **2.11.5**, `@tauri-apps/cli` 2.11.4, React 19.2.7,
Vite **8.1.5** (rolldown), TypeScript 5.9.3, Rust 1.96.0, Node 22.22.2. All three
previously-missing system packages are now installed.

**R1 — auth across the origin boundary: RESOLVED, and it was easier than feared.**

The plan proposed extending `_token_from_headers` to accept
`Authorization: Bearer`. **It already did** (`src/dax/web/auth.py:134-136`) —
that part of the plan was already true in the code. The only genuinely missing
piece was that `POST /api/auth/login` never handed the token back. Implemented:

- `LoginResponse` gained `token: str | None`; `/api/auth/login` and
  `/api/auth/setup` now return the signed token alongside the `Set-Cookie`.
- `is_authenticated` now validates **every** offered credential rather than only
  the first. Previously a present-but-stale cookie would shadow a valid bearer
  token and produce a 401 — a real bug for a desktop client that may hold both.
- `authenticate_websocket` additionally accepts an `Authorization: Bearer`
  header, alongside the cookie and the already-supported `?token=`.
- 13 new tests in `tests/unit/test_auth.py`; suite is 270 passing.

Verified over real HTTP against a live uvicorn (not just TestClient):
`GET /api/status` 401 → login → bearer-only client with no cookie jar 200 →
garbage bearer 401 → stale cookie alone 401 → stale cookie + valid bearer 200 →
cookie-only (the `web/` path) still 200.

**Measured webview origin (release build): `tauri://localhost`.**
Tauri v2 serves the custom protocol as `<scheme>://localhost` on Linux and
macOS, and `http://<scheme>.localhost` only on Windows/Android. Consequences:

1. **CORS: the backend must list `tauri://localhost` in `web.cors_origins`.**
   Confirmed: with it configured, the preflight `OPTIONS /api/auth/status`
   returns 200 and the follow-up `GET` returns 200 from the packaged app.
   Without it the backend answers **400 "Disallowed CORS origin"**. This is a
   config change, not a code change — but it is **mandatory**, and the app is
   dead in the water without it.
2. **CSP `connect-src` must name the backend.** WebKitGTK **does** honor port
   wildcards (verified): `http://127.0.0.1:* ws://127.0.0.1:*` works. That is
   what ships. **Known limitation:** the base URL is user-configurable at
   runtime but CSP is baked in at build time, so a backend on a *remote host*
   will be blocked by CSP until that host is added. Loopback is fine.

**R1 fallback — `?token=` on WebSockets: confirmed working.** `/ws/chat?token=`
connects with a valid token and is rejected without one.
Gotcha for M3: `/ws/logs` also rejects a *valid* token if the app was built with
a bare `create_app()` — the log buffer is wired by `DaxApp`, not `create_app`, so
the socket closes 1011 (which a client sees as a generic HTTP 403, identical to
an auth failure). Not an auth bug.

**Trap that cost real time — record it so nobody repeats it.** A plain
`cargo build` debug binary does **not** embed the frontend; Tauri points it at
`devUrl`. Run it standalone with no Vite dev server and you get a blank window,
no JS, and no network traffic — which looks exactly like "CSP/CORS is blocking
everything". Use `npm run tauri dev`, or `npm run tauri build` for a binary with
assets embedded. Note also that `cargo build` does **not** rebuild when only
`dist/` changed.

**R3 — Wayland HUD:** see Q9. Window creation works; positioning and exact
sizing do not.

**R4 — memory: THE PLAN'S BUDGET IS WRONG. This needs a user decision.**

| Build | RSS (3 procs) | PSS |
| --- | --- | --- |
| Debug, idle | 412.5 MB | 191.3 MB |
| **Release, idle on Login screen** | **422.7 MB** | **197.9 MB** |

D5 budgets **90–140 MB** for the whole app. We are at **1.4×–3× over that with
no features built** — no chat history, no log buffer, no waveform. The binary is
6.3 MB, so this is WebKitGTK's floor, not our code. R4's stated fallback
("reduce in-memory buffers") **cannot close a gap this size** — there are no
buffers yet to reduce.

D1 is a closed decision and this does not reopen it unilaterally, but D1's own
recorded caveat — that WebKitGTK is not universally lighter than Chromium — is
what actually happened. **Escalate:** either D5's number is revised to reflect
the platform (~200 MB PSS idle), or the stack decision gets revisited. Do not
quietly carry a budget that is already 3× breached.

**Routing:** hash routing adopted (`src/lib/useHashRoute.ts`), per 6.3's stated
safe fallback. No router dependency; history mode was not attempted.

**Bundling:** `.rpm` (2.9 MB) and `.deb` (2.9 MB) build successfully.
**AppImage fails** — `linuxdeploy` could not run in this environment. Deferred to
M6, where it belongs.

### M1 — Foundation: shell, auth, backend control (3–5 days)

- [ ] `desktop/` scaffold per 3.9
- [ ] Design tokens (`design/tokens.css`) implementing section 5
- [ ] Primitives needed for login + settings: `Button`, `TextInput`, `Field`,
      `Panel`, `PanelHeader`, `Toggle`, `Select`, `Badge`, `Toast`
- [ ] App shell: sidebar (5.9) + content area + light/dark/system theme
- [ ] Backend bearer-token support in `src/dax/web/auth.py` (3.5) + return the
      token from `POST /api/auth/login`
- [ ] HTTP client ported from `web/src/api/client.ts` with configurable base URL
      and bearer auth
- [ ] Login screen (parity per 6.2)
- [ ] Token in the OS keyring via Rust
- [ ] Rust: single-instance, tray icon, backend mode setting (remote only for now)
- [ ] Rust: `backend_status` polling `GET /api/health`
- [ ] Dashboard screen (read-only, proves the API works end to end)

**Gate:** launch the app, connect to a running backend, log in, see live status on
Dashboard. Measure RSS — record it.

#### M1 RESULTS — completed 2026-07-18. Gate: **PASSED WITH ONE CAVEAT.**

Built (all under `desktop/`):

- Scaffold per 3.9: Tauri v2 + Vite 8 + React 19 + TypeScript, **no HeroUI**,
  **no Tailwind** — CSS Modules + a token file, resolving Q6 in favour of CSS
  Modules per 6.3's lean.
- `src/design/tokens.css` — section 5 verbatim: type ramp, 8pt spacing, radii,
  elevation with the `.5px` hairline (plus a `max-resolution: 1.49dppx`
  fallback), both colour themes, spring easings, and the mandatory
  `prefers-reduced-motion` collapse.
- Primitives: `Button` (4 variants × 2 sizes), `TextInput`, `TextArea`,
  `Select`, `Field`, `Panel`/`PanelHeader`/`PanelBody`, `Toggle`, `Badge`,
  `Spinner`, `Toast`. Focus rings are `:focus-visible`-only per 5.8.
- App shell: 240px sidebar with the layered-opacity treatment from 3.6 (no blur
  — it is unavailable on Linux), 28px rows, hairline right edge, inline SVG
  icons, light/dark/system theming via the `.dark` class.
- Login screen with first-run setup, plus an inline control to repoint the app
  at a different backend origin.
- Dashboard: live status, MCP server list, voice toggle, 5s refresh.
- HTTP client ported from `web/src/api/client.ts` with an absolute base URL and
  bearer auth; status 0 is surfaced distinctly as "backend unreachable".
- Rust core: single-instance (second launch focuses the window), tray icon +
  menu, keyring-backed token storage with a documented in-memory fallback when
  the Secret Service is unavailable, `backend_status` health probe, and a
  `backend_set_mode` that currently accepts remote only.
- Backend bearer-token support — see the M0 results above.

Verified: `npx tsc -b` clean, `cargo clippy --all-targets` clean, `cargo fmt
--check` clean, release build + `.rpm` bundle succeed, app launches and reaches
the backend from `tauri://localhost` (CORS preflight 200, `/api/auth/status`
200), backend suite 270 passing with `ruff` clean.

**Caveat on the gate — read this.** "Log in and see live status on Dashboard"
was verified *by construction and by protocol*, not by a human clicking. The
GNOME Wayland screenshot portal denies capture from this environment, so the
rendered UI could not be seen and the login form could not be driven. What was
actually proven: the packaged app boots, executes its JS, and completes an
authenticated round-trip to the backend; and the exact login→bearer→protected-route
sequence the UI performs was exercised end to end over real HTTP with curl. The
unproven residue is purely visual — that the rendered pixels look right. **A
human should launch it once and confirm.**

**Deliberately not done in M1** (deferred, not forgotten): backend sidecar
supervision (3.7 option A — remote mode covers the systemd case and is the
default per Q1), global hotkeys, autostart, the voice HUD window, and shared
types with `web/` (M5).

### M2 — Chat (5–8 days)

- [ ] `useChatSocket` ported with bearer/`?token=` auth
- [ ] Conversation sidebar with list, search, load, delete
- [ ] Message list, markdown, syntax highlighting
- [ ] Live thinking trail + collapsible thought log
- [ ] Tool confirmation modal with countdown
- [ ] Model selector
- [ ] Activity panel
- [ ] Reconnect handling + connection status
- [ ] Session id persistence

**Gate:** hold a full conversation including at least one `ask`-classified tool
requiring confirmation. Verify a denied timeout behaves correctly. Measure RSS.

### M3 — Settings + remaining screens (6–10 days)

- [ ] Remaining primitives: `Modal`, `Sheet`, `Popover`, `Tooltip`, `Tabs`,
      `SegmentedControl`, `Slider`, `List`, `EmptyState`, `CodeBlock`
- [ ] Settings shell with tabs
- [ ] General, LLM, Tools, Server, Telegram, WhatsApp tabs
- [ ] Memory tab
- [ ] MCP tab + MCP screen + export panel
- [ ] MCP Marketplace
- [ ] Shell/Commands screen
- [ ] Logs screen (**virtualized**, merged with sidecar output)
- [ ] Voice settings tab (config only — no HUD yet)

**Gate:** every checklist item in 6.2 except the voice HUD is checked. Measure RSS
with the log viewer holding 10k lines.

### M4 — Voice: backend `/ws/voice` + HUD (4–6 days)

Backend work first:
- [ ] `src/dax/web/routes/voice_ws.py` per the requirements in 4.6
- [ ] `voice_events_from_app` in `src/dax/web/dependencies.py`
- [ ] Register under `/ws` in `src/dax/web/server.py`
- [ ] `tests/unit/test_voice_ws.py`

Then the client:
- [ ] `useVoiceSocket` hook
- [ ] Voice HUD window (7.2)
- [ ] Canvas 2D waveform with spring interpolation and **verified idle stop** (7.4)
- [ ] HUD state visuals (7.3)
- [ ] Transcript display
- [ ] Speaker-verification indicator
- [ ] Global hotkey (push-to-talk + summon)
- [ ] Tray voice controls
- [ ] Voice enrollment + gallery screens

**Gate:** trigger the wake word, watch the waveform track the voice live, see the
transcript, hear the reply with the output waveform. **Then confirm with a
profiler that CPU returns to ~0% within 2 s of returning to idle.** This is the
D5 gate — do not wave it through.

### M5 — Polish and unification (3–5 days)

- [ ] Shared type package between `web/` and `desktop/` (3.9)
- [ ] Native notifications
- [ ] Autostart
- [ ] Keyboard shortcuts throughout; full keyboard navigability
- [ ] Focus-ring audit (5.8)
- [ ] `prefers-reduced-motion` audit
- [ ] Empty/loading/error states for every screen
- [ ] Accessibility pass: labels, roles, contrast

**Gate:** the app is navigable end to end with the keyboard only.

### M6 — Packaging and distribution (2–4 days)

- [ ] Icons at all required sizes
- [ ] `tauri.conf.json` bundle metadata
- [ ] Build `.rpm` (primary — this is Fedora), `.deb`, AppImage
- [ ] Evaluate Flatpak — see 11.4
- [ ] Decide on the Python sidecar (3.7 option B) or ship remote-mode only
- [ ] Install/uninstall verification on a clean Fedora 44
- [ ] Update `README.md` and `CLAUDE.md`

**Gate:** install the RPM on a clean system, launch from the desktop menu, connect
to a backend.

### M7 — Remote audio source (optional, 4–6 days)

- [ ] `AudioSource` protocol + `LocalAudioSource` refactor in
      `src/dax/voice/pipeline.py`
- [ ] `RemoteAudioSource` fed by inbound `/ws/voice` binary frames
- [ ] Desktop-side PCM capture (Rust `cpal` or TS `AudioWorklet` — decide here)
- [ ] Backend-mode UI exposing local vs remote audio

**Gate:** run the backend on another host, talk to it from the desktop.

---

## 11. Build, dev, and release setup

### 11.1 Fedora 44 system dependencies

Verified state on this machine (2026-07-18, via `rpm -q`):

**Already installed** — `webkit2gtk4.1-devel` 2.52.5, `libsoup3-devel` 3.6.6,
`webkit2gtk4.1` 2.52.5, `libsoup3` 3.6.6, `gtk3-devel` 3.24.52, `openssl-devel`
3.5.7.

**Missing — install these** (all three verified absent via `rpm -q`):

```bash
sudo dnf install librsvg2-devel libxdo-devel libappindicator-gtk3-devel
```

The full package list from Tauri's prerequisites page for Fedora/RHEL, for
reference:

```bash
sudo dnf check-update
sudo dnf install webkit2gtk4.1-devel openssl-devel curl wget file \
  libappindicator-gtk3-devel librsvg2-devel libxdo-devel gcc gcc-c++ make
sudo dnf group install 'c-development'
```

> `libappindicator-gtk3-devel` is listed by Tauri for tray support and is
> **confirmed missing** on this machine. The tray is a Milestone 1 deliverable,
> so this is not optional.

Toolchain (verified present): Rust 1.96.0 stable, Cargo 1.96.0, Node v22.22.2.
Tauri's docs do not state minimum Rust/Node versions beyond "stable" and "LTS";
1.96.0 and Node 22 LTS comfortably satisfy both.

### 11.2 Tauri versions

Verified from crates.io on 2026-07-18:

- `tauri` crate: **2.11.5**, released 2026-07-01 (max stable = newest)
- `@tauri-apps/cli`: 2.11.4
- `tauri-bundler`: 2.9.4
- `wry`: 0.55.1
- `tao`: 0.35.3

Tauri 2.0 stable shipped 2024-10-02. Pin exact versions in `Cargo.toml` and
`package.json`; do not use `^` ranges for the Tauri crates.

### 11.3 Dev workflow

```bash
# from desktop/
npm install
npm run tauri dev       # Vite dev server + Tauri window with hot reload

# type check
npx tsc -b

# production build
npm run tauri build
```

Backend during development — either:

```bash
~/.local/bin/uv run dax                    # serves http://127.0.0.1:8420
```

or the systemd user unit from `scripts/install.sh`.

**Required backend config — MANDATORY, verified in M0.** The webview origin is
**`tauri://localhost`** on Linux. It must be in `web.cors_origins`:

```toml
[web]
cors_origins = ["tauri://localhost"]
```

Without it every request fails the preflight with **400 "Disallowed CORS
origin"** and the app shows "Backend unreachable". The bearer-token approach
(3.5) removes the *cookie* problem but not the CORS one — the `Authorization`
header makes every request preflighted.

For `npm run tauri dev` the webview loads from the Vite dev server instead, so
the origin is **`http://localhost:5273`** — add that too when developing, or
enable `web.dev_mode` (which whitelists `http://localhost:5173`, the *web* dev
port, not this one — per `src/dax/web/server.py:71-73`).

### 11.4 Packaging

Tauri v2 documents these Linux targets: **AppImage**, **Debian (.deb)**,
**RPM (.rpm)**, **Snapcraft**, and **AUR**. Flatpak is mentioned in the
distribution overview prose but has **no dedicated documentation page**
— **UNCERTAIN** whether the bundler produces Flatpak natively; assume it does not
and that Flatpak requires an external manifest.

Recommendation, in priority order:

1. **RPM** — primary. This is a Fedora 44 machine.
2. **AppImage** — secondary. Portable, no install, good for testing.
3. **deb** — free from the same bundler run; ship it.
4. **Flatpak** — defer. If wanted, write a `org.dax.Desktop.yaml` manifest
   wrapping the built binary. Note that Flatpak sandboxing will complicate the
   Python sidecar and mic access considerably — a real argument for remote-mode
   default (3.7).

Configure in `tauri.conf.json`:

```json
{
  "bundle": {
    "active": true,
    "targets": ["rpm", "deb", "appimage"],
    "identifier": "dev.dax.desktop",
    "icon": ["icons/32x32.png", "icons/128x128.png", "icons/icon.png"]
  }
}
```

**Code signing / updater:** not needed for single-user self-hosted use. Skip the
Tauri updater plugin unless the user asks — it adds key management for no benefit
here.

---

## 12. Open questions requiring user input

Answer these before or during M0. Record answers inline in this document.

**Q1. Backend lifecycle — which mode is the default?**
(a) Desktop spawns the backend as a sidecar; (b) desktop connects to the
already-running systemd user unit. This plan recommends **(b)** as the default and
(a) as an option, because it makes the app useful immediately without solving
Python packaging (3.7). Confirm.

**Q2. Is macOS ever a target?**
D3 specifies a macOS-inspired design, but the machine is Fedora. If macOS is
never a target, drop the `window-vibrancy` dependency and all vibrancy code paths
entirely, and design purely for the Linux fallback (3.6). If it is a future
target, keep the platform-conditional structure. This meaningfully changes how
much complexity the sidebar carries.

**Q3. Native window decorations, or a custom titlebar?**
This plan recommends **native decorations** initially (3.6) because Wayland makes
custom chrome expensive and error-prone. A custom titlebar is more "macOS", but
it will fight the compositor. Which do you want?

**Q4. Does the desktop app replace the web UI, or coexist?**
This plan assumes coexistence (section 8). If the desktop app is intended to
replace `web/`, the `web/` maintenance burden and the shared-types work
(3.9, M5) change substantially.

**Q5. Global hotkey binding.**
What should the defaults be? Suggestion: `Super+Shift+D` to summon,
`Super+Space` held for push-to-talk (note `Super+Space` may collide with GNOME's
input-source switcher on Fedora).

**Q6. Tailwind v4 or CSS Modules?**
6.3 leans CSS Modules for finer control, but notes either is defensible. If you
have a preference, state it now; otherwise the implementing agent decides and
does not revisit.

**Q7. Is Flatpak actually wanted?**
It is meaningful extra work and it complicates the sidecar and microphone access.
RPM + AppImage may be sufficient.

**Q8 (from M0).** Does cookie auth survive the Tauri webview origin boundary?
— *Answer (measured 2026-07-18, release build, Fedora 44 / GNOME / Wayland):*
**Moot — we no longer depend on it.** The measured production webview origin is
`tauri://localhost` (a non-HTTP scheme). Rather than characterise WebKitGTK's
cookie policy for a custom scheme, M0 shipped the bearer-token path (3.5) and
the desktop client uses it exclusively. Verified end to end over real HTTP: a
client holding only the token, with **no cookie jar at all**, authenticates
successfully; a stale cookie no longer shadows a valid bearer token. Cookie auth
for `web/` is untouched and still passes.

**Q9 (from M0).** Does transparent/always-on-top window positioning work under
GNOME/Wayland on Fedora 44? — *Answer:* **Partly.**
- Creating a `decorations:false, transparent:true, alwaysOnTop:true,
  skipTaskbar:true` window: **works.**
- `set_position(640, 900)` then `outer_position()` reads back **(0, 0)** —
  Wayland does **not** honor programmatic positioning. Confirmed, no longer
  UNCERTAIN. The M4 HUD must accept compositor placement.
- `inner_size(380, 140)` came back as **470×290** physical px. Logical sizing is
  also not honored exactly; size the HUD from the size you actually get, do not
  assume the requested value.
- Shadow clipping could **not** be verified — the GNOME Wayland screenshot
  portal denies capture from a non-interactive session.

**Q10 (from M0).** Baseline RSS of an empty Tauri window on this machine?
— *Answer:* **Far over the D5 budget. See the R4 finding in section 10 (M0
results).** Release build, idle on the Login screen, no features:
**422.7 MB RSS / 197.9 MB PSS** across 3 processes. The app binary is only
6.3 MB — this is WebKitGTK, not our code. **D5 (90–140 MB) is not achievable on
this stack on this machine and needs a user decision.**

---

## 13. How to continue this work — for a cold agent

You have no memory of the conversation that produced this document. Here is what
to do.

### 13.1 Orient

1. Read `CLAUDE.md` at the repo root. It documents the backend architecture
   authoritatively.
2. Read section 2 of this file. Those decisions are **closed**. If you find
   yourself writing "we should consider Electron instead" — stop.
3. A graphify knowledge graph exists at `graphify-out/graph.json`. Prefer it over
   raw greps for orientation:
   ```
   graphify query "<question>"
   graphify explain "<symbol>"
   graphify path "<A>" "<B>"
   ```
   Note: `graphify query` returns noisy results on broad questions and includes
   minified nodes from `src/dax/web/static/assets/*.js`. Ignore those. For
   precise route/protocol facts, section 4 of this document is more reliable than
   re-deriving from the graph.

### 13.2 Find your place

Check `desktop/` for what exists. If it contains only `PLAN.md`, start at **M0**
(section 10). Otherwise find the first milestone whose gate has not been met.

Every milestone has an explicit **Gate**. A milestone is not done until its gate
passes. Do not batch milestones.

### 13.3 Ground truth files

When this document and the code disagree, **the code wins** — update this
document.

| Question | Authoritative file |
| --- | --- |
| HTTP routes | `src/dax/web/routes/*.py` |
| Route mounting, auth wiring, CORS | `src/dax/web/server.py` |
| Auth mechanism | `src/dax/web/auth.py` (esp. `:114-151`) |
| Chat WS protocol | `src/dax/web/routes/chat.py:71-135` |
| Agent event shapes | `src/dax/orchestrator/agent.py:270,349,357,387` |
| Tool confirmation shapes | `src/dax/orchestrator/approval.py:87-119` |
| Logs WS | `src/dax/web/routes/logs.py` |
| Voice event transport | `src/dax/core/voice_events.py` |
| Voice DSP frame shape | `src/dax/voice/events.py` |
| Pipeline states + emit sites | `src/dax/voice/pipeline.py:102-109,261-276,554-576,992,1001` |
| Existing API client (port this) | `web/src/api/client.ts` |
| Existing config types | `web/src/types/config.ts` |
| Existing chat WS client (port this) | `web/src/hooks/useChatSocket.ts` |
| Existing UI primitives (API reference) | `web/src/components/ui.tsx` |
| Screen behavior to match | `web/src/pages/**` |

### 13.4 Rules of engagement

- **Do not modify `web/`** unless a milestone explicitly says to. The two clients
  coexist (section 8).
- **Backend changes are allowed but must be minimal and additive.** The three
  planned ones: bearer-token auth (3.5, M1), `/ws/voice` (4.6, M4), pluggable
  audio source (7.6, M7). Anything else, ask.
- If you change the backend, follow `CLAUDE.md`'s conventions: `~/.local/bin/uv
  run ruff check src tests`, `~/.local/bin/uv run mypy src` (strict), and add
  tests.
- **Measure RSS at every milestone gate** and record it here. D5 is a hard
  requirement, not an aspiration.
- Anything marked **UNCERTAIN** in this document is a research task. Resolve it
  and replace the marker with the finding — do not build on top of an unresolved
  uncertainty.
- Update section 12 as questions get answered.

### 13.5 First concrete action

```bash
sudo dnf install librsvg2-devel libxdo-devel libappindicator-gtk3-devel
```

(Target triple is already known: `x86_64-unknown-linux-gnu`.)

Then begin M0.

---

## 14. Sources

Settings information architecture (section 6.0), consulted 2026-07-19:

- [Settings — Apple Human Interface Guidelines](https://developers.apple.com/design/human-interface-guidelines/patterns/settings/)
  — prefer context-specific settings; reserve a settings area for what genuinely
  applies app-wide.
- [User and workspace settings — VS Code](https://code.visualstudio.com/docs/getstarted/settings)
  — the search-first model: searching filters non-matching settings out rather
  than merely highlighting matches.
- [What is progressive disclosure in UX? — UXPin](https://www.uxpin.com/studio/blog/what-is-progressive-disclosure/)
- [Progressive disclosure: types and use cases — LogRocket](https://blog.logrocket.com/ux-design/progressive-disclosure-ux-types-use-cases/)
  — source of the "keep disclosure below three levels" constraint; past that,
  layering increases cognitive load instead of reducing it.

Research consulted for this document (2026-07-18):

- [Tauri Core Ecosystem Releases](https://v2.tauri.app/release/)
- [tauri crate on crates.io](https://crates.io/crates/tauri) — v2.11.5, 2026-07-01
- [Tauri v2 Prerequisites](https://v2.tauri.app/start/prerequisites/) — Fedora deps
- [Tauri v2 Sidecar / Embedding External Binaries](https://v2.tauri.app/develop/sidecar/)
- [Tauri v2 Capabilities](https://v2.tauri.app/security/capabilities/)
- [Tauri v2 Distribute](https://v2.tauri.app/distribute/)
- [tauri-apps/window-vibrancy](https://github.com/tauri-apps/window-vibrancy) — Linux unsupported
- [Tauri discussion #15371 — GTK frame extents on Wayland](https://github.com/orgs/tauri-apps/discussions/15371)
- [Tauri issue #5889 — memory benchmark accuracy](https://github.com/tauri-apps/tauri/issues/5889)
- [Apple HIG — Typography](https://developer.apple.com/design/human-interface-guidelines/typography)
- [SF Pro typography system](https://blakecrosley.com/blog/sf-pro-typography-system)
- [Canvas vs WebGL renderer comparison](https://simplified.media/guides/canvas-vs-webgl)
- [SVG vs Canvas vs WebGL 2026 performance comparison](https://www.svggenie.com/blog/svg-vs-canvas-vs-webgl-performance-2025)
