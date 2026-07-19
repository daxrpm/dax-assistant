"""Single-user authentication for the web UI and API.

Dax is a personal assistant: one user, one password. We store an argon2 hash
of the password (never the password itself) and hand out signed, expiring
session cookies on login.

Secrets come from the environment (see ``.env``):
  - ``DAX_SECURITY__PASSWORD_HASH``   argon2 hash of the login password
  - ``DAX_SECURITY__SESSION_SECRET``  random string used to sign cookies

Generate a password hash from the command line::

    python -m dax.web.auth "my-super-secret-password"
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

if TYPE_CHECKING:
    from fastapi import Response, WebSocket

    from dax.core.config import SecurityConfig

logger = logging.getLogger(__name__)

_hasher = PasswordHasher()

# Salt namespaces the signer so a session secret reused elsewhere can't be
# cross-used to forge Dax sessions.
_SIGNER_SALT = "dax.session.v1"
_SESSION_SUBJECT = "dax-user"


def hash_password(password: str) -> str:
    """Return an argon2id hash of ``password``."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Check ``password`` against a stored argon2 hash."""
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


class AuthManager:
    """Validates logins and issues/validates signed session tokens.

    Lives on ``app.state.auth`` and is consulted by the ``require_auth``
    dependency and the WebSocket handshake.
    """

    def __init__(self, config: SecurityConfig) -> None:
        self._enabled = config.auth_enabled
        self._password_hash = config.password_hash
        self._ttl_seconds = max(1, config.session_ttl_hours) * 3600
        self.cookie_name = config.cookie_name
        self.cookie_secure = config.cookie_secure

        secret = config.session_secret
        if not secret:
            # Ephemeral secret: logins work, but sessions don't survive a
            # restart. Fine for first run; warn so the user sets a real one.
            secret = secrets.token_urlsafe(48)
            if self._enabled:
                logger.warning(
                    "No DAX_SECURITY__SESSION_SECRET set — using an ephemeral "
                    "secret; sessions will be invalidated on restart."
                )
        self._serializer = URLSafeTimedSerializer(secret, salt=_SIGNER_SALT)

        if self._enabled and not self._password_hash:
            logger.warning(
                "Auth is enabled but no DAX_SECURITY__PASSWORD_HASH is set — "
                "login is impossible. Generate one with "
                "`python -m dax.web.auth <password>`."
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def configured(self) -> bool:
        """True when a password is set (login is possible)."""
        return bool(self._password_hash)

    def verify_login(self, password: str) -> bool:
        return verify_password(self._password_hash, password)

    def issue_token(self) -> str:
        return self._serializer.dumps({"sub": _SESSION_SUBJECT})

    def validate_token(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            self._serializer.loads(token, max_age=self._ttl_seconds)
        except (BadSignature, SignatureExpired):
            return False
        return True

    def set_cookie(self, response: Response, token: str) -> None:
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            max_age=self._ttl_seconds,
            httponly=True,
            samesite="lax",
            secure=self.cookie_secure,
            path="/",
        )

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(key=self.cookie_name, path="/")

    # -- request helpers --

    @staticmethod
    def _bearer_token(header: str | None) -> str | None:
        """Extract the token from an ``Authorization: Bearer <token>`` header."""
        if not header:
            return None
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer":
            return None
        return value.strip() or None

    def _token_candidates(self, request: Request) -> list[str]:
        """Every credential the request offers, in preference order.

        The browser SPA sends a cookie; the desktop client sends a bearer
        token. Both are collected so a stale cookie can't shadow a valid
        bearer token (or vice versa) — ``is_authenticated`` accepts if *any*
        candidate validates.
        """
        candidates = [
            request.cookies.get(self.cookie_name),
            self._bearer_token(request.headers.get("authorization")),
        ]
        return [token for token in candidates if token]

    def _token_from_headers(self, request: Request) -> str | None:
        """First offered credential, or ``None``. Kept for compatibility."""
        candidates = self._token_candidates(request)
        return candidates[0] if candidates else None

    def is_authenticated(self, request: Request) -> bool:
        if not self._enabled:
            return True
        return any(self.validate_token(token) for token in self._token_candidates(request))

    def authenticate_websocket(self, websocket: WebSocket) -> bool:
        """Validate a WebSocket via cookie, ``?token=``, or bearer header."""
        if not self._enabled:
            return True
        candidates = [
            websocket.cookies.get(self.cookie_name),
            websocket.query_params.get("token"),
            self._bearer_token(websocket.headers.get("authorization")),
        ]
        return any(self.validate_token(token) for token in candidates if token)


def require_auth(request: Request) -> None:
    """FastAPI dependency that rejects unauthenticated requests with 401."""
    auth: AuthManager | None = getattr(request.app.state, "auth", None)
    if auth is None:
        # Auth not wired (shouldn't happen) — fail closed.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Auth not configured")
    if not auth.is_authenticated(request):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _main() -> None:
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m dax.web.auth <password>", file=sys.stderr)
        raise SystemExit(2)
    print(hash_password(sys.argv[1]))


if __name__ == "__main__":
    _main()
