"""LLM provider adapters implementing the LLMProvider port.

Each adapter wraps one official SDK (anthropic, openai, google-genai) or an
OpenAI-compatible endpoint (Ollama / any API). They consume the OpenAI chat
message format produced by ``dax.llm.client.build_messages_for_llm`` and return
a domain ``Message``, keeping the orchestrator provider-agnostic.
"""

from __future__ import annotations

from dax.llm.providers.anthropic_provider import AnthropicProvider
from dax.llm.providers.gemini_provider import GeminiProvider
from dax.llm.providers.openai_provider import OpenAIProvider

__all__ = ["AnthropicProvider", "GeminiProvider", "OpenAIProvider"]
