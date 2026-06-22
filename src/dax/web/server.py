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
from dax.web.routes import api, auth, chat, logs, oauth, webhooks
from dax.web.spa_middleware import SPAStaticFiles

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from dax.core.config import DaxConfig
    from dax.orchestrator.bus import MessageBus


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
        app.state.auth = AuthManager(config.security)
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "apikey"],
    )

    # Public auth endpoints (login/logout/status) — how you get a session.
    app.include_router(auth.router, prefix="/api")
    # Protected API + OAuth routes require a valid session.
    protected = [Depends(require_auth)]
    app.include_router(api.router, prefix="/api", dependencies=protected)
    app.include_router(oauth.router, prefix="/api", dependencies=protected)
    # Chat + logs WS authenticate in their own handshake; webhooks use a secret.
    app.include_router(chat.router, prefix="/ws")
    app.include_router(logs.router, prefix="/ws")
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
