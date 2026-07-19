"""FastAPI application factory.

Creates the web server with lifespan management, CORS, routes, and static files.
Uses the modern asynccontextmanager lifespan pattern (NOT deprecated on_event).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dax.web.auth import AuthManager, require_auth
from dax.web.routes import (
    auth,
    chat,
    conversations,
    devices,
    logs,
    mcp,
    memory,
    oauth,
    system,
    voice,
    voice_ws,
    webhooks,
)
from dax.web.routes import (
    config as config_routes,
)
from dax.web.spa_middleware import SPAStaticFiles

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from dax.core.config import DaxConfig
    from dax.orchestrator.bus import MessageBus


# Webview origins used by the bundled desktop app. WebKitGTK (Linux) and WKWebView
# (macOS) serve from the custom protocol; WebView2 (Windows) uses the http form.
_DESKTOP_ORIGINS = ("tauri://localhost", "http://tauri.localhost")
_LOCAL_DEV_ORIGIN_PATTERN = r"^http://(?:localhost|127\.0\.0\.1):(?:5173|5273)$"


def create_app(
    config: DaxConfig,
    bus: MessageBus,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.config = config
        app.state.bus = bus
        app.state.voice_listening = config.voice.enabled
        # Reuse the eagerly-built manager rather than constructing a second
        # one: by the time the lifespan runs, DaxApp.start() may already have
        # attached the device registry and `/auth/setup` may have set the
        # password hash in place. Replacing the instance would drop both.
        app.state.auth = _auth
        yield

    # Build auth eagerly too so routes work under TestClient (which may not
    # always run the lifespan) and the dependency always finds app.state.auth.
    _auth = AuthManager(config.security)

    app = FastAPI(
        title="Dax Assistant",
        description="Voice-first personal AI assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )
    # Available immediately (not only after lifespan) so require_auth and the
    # WebSocket handshake always find it.
    app.state.auth = _auth

    # CORS — allow the Vite dev server origin only in dev mode.
    origins = list(config.web.cors_origins)
    if config.web.dev_mode:
        origins.append("http://localhost:5173")
    # The bundled desktop app is a first-class client shipped from this repo,
    # so its webview origins belong in the allowlist by construction rather
    # than in user config. Leaving it configurable meant a fresh install was
    # dead on arrival, and any settings save from the running app rewrites the
    # whole config document — silently clobbering a hand-edited entry.
    # WebKitGTK uses tauri://localhost; Windows/WebView2 uses the http form.
    origins.extend(o for o in _DESKTOP_ORIGINS if o not in origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Vite serves the browser and Tauri development clients on fixed local
        # ports. Keep this narrow: arbitrary localhost origins are not trusted.
        allow_origin_regex=_LOCAL_DEV_ORIGIN_PATTERN,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "apikey"],
    )

    # Public auth endpoints (login/logout/status) — how you get a session.
    app.include_router(auth.router, prefix="/api")
    # Device pairing/enrolment carries its own gating: pairing and revocation
    # need a session, enrolment needs a one-time code, token exchange needs the
    # device secret. So it must not sit behind the blanket `protected` list.
    app.include_router(devices.router, prefix="/api")
    # Protected API + OAuth routes require a valid session. The former api.py
    # god-module is now split into cohesive domain routers.
    protected = [Depends(require_auth)]
    for domain_router in (
        system.router,
        config_routes.router,
        mcp.router,
        conversations.router,
        memory.router,
        voice.router,
    ):
        app.include_router(domain_router, prefix="/api", dependencies=protected)
    app.include_router(oauth.router, prefix="/api", dependencies=protected)
    # Chat + logs + voice WS authenticate in their own handshake; webhooks use
    # a secret.
    app.include_router(chat.router, prefix="/ws")
    app.include_router(logs.router, prefix="/ws")
    app.include_router(voice_ws.router, prefix="/ws")
    app.include_router(webhooks.router, prefix="/webhook")

    # SPA static files — serves built React app with index.html fallback
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        app.mount(
            "/",
            SPAStaticFiles(directory=str(static_dir), html=True),
            name="spa",
        )

    return app
