"""OpenAI Codex CLI provider.

Runs ``codex exec --json`` as a subprocess to use the user's ChatGPT plan
(via ``~/.codex/auth.json``) or ``CODEX_API_KEY``. Codex runs its OWN agentic
loop and tools, so this provider returns plain text only — it does NOT use
Dax's tool-calling pipeline. To give Codex access to MCP servers, generate its
``~/.codex/config.toml`` from the MCP section (servers flagged export_codex).

Reference: https://developers.openai.com/codex/noninteractive
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any

from dax.core.exceptions import LLMError, LLMTimeoutError
from dax.core.models import Message, MessageRole

logger = logging.getLogger(__name__)


class CodexProvider:
    """Implements the LLMProvider port over the Codex CLI (`codex exec`)."""

    def __init__(
        self,
        *,
        name: str = "codex",
        binary: str = "codex",
        model: str = "",
        timeout: int = 300,
    ) -> None:
        self._name = name
        self._binary = binary
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def _flatten_prompt(messages: list[dict[str, Any]]) -> str:
        """Collapse the chat history into a single prompt string for Codex.

        Codex exec takes one task string, not a message array, so we render the
        conversation as a readable transcript and let Codex answer the last
        user turn in context.
        """
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content or role == "tool":
                continue
            if role == "system":
                parts.append(f"[System instructions]\n{content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        return "\n\n".join(parts)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Message:
        # tools are intentionally ignored — Codex manages its own tool loop.
        prompt = self._flatten_prompt(messages)

        argv = [self._binary, "exec", "--json", "--skip-git-repo-check"]
        if self._model:
            argv += ["--model", self._model]
        argv.append(prompt)

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise LLMError(
                f"Codex binary '{self._binary}' not found. Install it with "
                "`npm install -g @openai/codex` and run `codex login`."
            ) from e

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError as e:
            proc.kill()
            raise LLMTimeoutError(f"Codex timed out after {self._timeout}s") from e

        if proc.returncode != 0:
            err = stderr.decode("utf-8", "replace").strip()
            raise LLMError(f"Codex exited {proc.returncode}: {err[:300]}")

        text = self._extract_final_message(stdout.decode("utf-8", "replace"))
        return Message(role=MessageRole.ASSISTANT, content=text)

    @staticmethod
    def _extract_final_message(raw: str) -> str:
        """Parse the JSONL event stream and return the final agent message."""
        final = ""
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            # The final assistant text arrives as an agent_message item.
            item = event.get("item") or event
            itype = item.get("item_type") or item.get("type") or ""
            if "message" in itype:
                txt = item.get("text") or item.get("content") or ""
                if isinstance(txt, str) and txt.strip():
                    final = txt
        return final.strip() or "(Codex returned no message.)"

    async def is_available(self) -> bool:
        return shutil.which(self._binary) is not None or self._binary not in ("codex",)
