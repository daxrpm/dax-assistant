"""Conversation history endpoints — list, fetch, delete web chats."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from dax.web.dependencies import get_repository

router = APIRouter(tags=["conversations"])


@router.get("/conversations")
async def list_conversations(request: Request, limit: int = 50) -> list[dict[str, Any]]:
    """List recent web conversations for the sidebar."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        return []
    return await repo.list_conversations("web", limit=limit)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
    """Return a conversation with its messages."""
    repo = get_repository(request)
    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": conv.id,
        "session_key": conv.session_key,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role.value,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in conv.messages
            if m.role.value in ("user", "assistant")
        ],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, request: Request) -> None:
    """Delete a conversation and its messages."""
    repo = get_repository(request)
    await repo.delete_conversation(conversation_id)
