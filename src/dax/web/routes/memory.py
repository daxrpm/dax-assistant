"""Long-term memory endpoints — CRUD over user-curated ``*.md`` fact files.

These files are read back into the agent's system prompt (see
``Agent._memory_block``), so editing here directly shapes what the assistant
"remembers" about the user.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["memory"])

_MEMORY_TYPES = {"user", "feedback", "project", "reference"}


def _memory_dir(request: Request, *, create: bool = False) -> Path:
    config = request.app.state.config
    raw = getattr(config, "memory_path", "") or "~/.dax/memory"
    p = Path(raw).expanduser()
    if create:
        p.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    if not p.is_dir():
        raise HTTPException(status_code=500, detail="memory_path is not a directory")
    return p


def _memory_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    if not slug:
        slug = "memory"
    return slug[:80]


def _memory_path(mem_dir: Path, slug: str) -> Path:
    clean = _memory_slug(slug)
    path = (mem_dir / f"{clean}.md").resolve()
    root = mem_dir.resolve()
    if root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid memory slug")
    return path


def _memory_frontmatter(
    *,
    name: str,
    description: str = "",
    mem_type: str = "user",
    body: str = "",
) -> str:
    safe_type = mem_type if mem_type in _MEMORY_TYPES else "user"
    return (
        "---\n"
        f"name: {name.strip() or 'Memory'}\n"
        f"description: {description.strip()}\n"
        f"type: {safe_type}\n"
        "---\n\n"
        f"{body.strip()}\n"
    )


def _parse_memory_file(path: Path) -> dict[str, Any]:
    """Parse a memory .md file and return structured data."""
    text = path.read_text(encoding="utf-8")
    slug = path.stem
    name = slug
    description = ""
    mem_type = "user"
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()
            for line in fm_text.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif "type:" in line:
                    mem_type = line.split(":", 1)[1].strip()

    return {
        "slug": slug,
        "name": name,
        "description": description,
        "type": mem_type,
        "body": body,
        "filename": path.name,
    }


def _refresh_memory_index(mem_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for p in sorted(mem_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        try:
            entries.append(_parse_memory_file(p))
        except Exception:
            pass
    lines = ["# Dax Memory", ""]
    if entries:
        lines.extend(
            f"- [{entry['name']}]({entry['filename']}) - {entry['description']}"
            for entry in entries
        )
    else:
        lines.append("_No memories yet._")
    (mem_dir / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


class MemoryCreate(BaseModel):
    name: str
    body: str = ""
    description: str = ""
    type: str = "user"


class MemoryUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    description: str | None = None
    type: str | None = None


@router.get("/memory")
async def list_memory(request: Request) -> list[dict[str, Any]]:
    """List all memory entries."""
    mem_dir = _memory_dir(request, create=True)
    entries = []
    for p in sorted(mem_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        try:
            entries.append(_parse_memory_file(p))
        except Exception:
            pass
    return entries


@router.get("/memory/{slug}")
async def get_memory(slug: str, request: Request) -> dict[str, Any]:
    mem_dir = _memory_dir(request, create=True)
    path = _memory_path(mem_dir, slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Memory not found")
    return _parse_memory_file(path)


@router.post("/memory", status_code=201)
async def create_memory(request: Request, body: MemoryCreate) -> dict[str, Any]:
    mem_dir = _memory_dir(request, create=True)
    base_slug = _memory_slug(body.name)
    slug = base_slug
    i = 2
    while _memory_path(mem_dir, slug).exists():
        slug = f"{base_slug}-{i}"
        i += 1
    path = _memory_path(mem_dir, slug)
    path.write_text(
        _memory_frontmatter(
            name=body.name,
            description=body.description,
            mem_type=body.type,
            body=body.body,
        ),
        encoding="utf-8",
    )
    _refresh_memory_index(mem_dir)
    return _parse_memory_file(path)


@router.patch("/memory/{slug}")
async def update_memory(slug: str, request: Request, body: MemoryUpdate) -> dict[str, str]:
    mem_dir = _memory_dir(request, create=True)
    path = _memory_path(mem_dir, slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Memory not found")

    existing = _parse_memory_file(path)
    path.write_text(
        _memory_frontmatter(
            name=body.name if body.name is not None else existing["name"],
            description=(
                body.description
                if body.description is not None
                else existing["description"]
            ),
            mem_type=body.type if body.type is not None else existing["type"],
            body=body.body if body.body is not None else existing["body"],
        ),
        encoding="utf-8",
    )
    _refresh_memory_index(mem_dir)
    return {"status": "ok"}


@router.delete("/memory/{slug}", status_code=204)
async def delete_memory(slug: str, request: Request) -> None:
    mem_dir = _memory_dir(request, create=True)
    path = _memory_path(mem_dir, slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Memory not found")
    path.unlink()
    _refresh_memory_index(mem_dir)
