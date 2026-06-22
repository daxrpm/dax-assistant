"""SPA-aware static file serving.

Subclasses Starlette's StaticFiles to return index.html for paths
that don't match a file — enabling React Router client-side navigation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for SPA routing.

    For any path that doesn't match a real static file,
    returns index.html so React Router can handle the route.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
            if response.status_code >= 400:
                return await self._serve_index()
            return response
        except Exception:
            return await self._serve_index()

    async def _serve_index(self) -> Response:
        """Serve index.html as fallback."""
        for directory in self.all_directories:
            index_path = Path(str(directory)) / "index.html"
            if index_path.is_file():
                return FileResponse(str(index_path))
        return Response("Not Found", status_code=404)
