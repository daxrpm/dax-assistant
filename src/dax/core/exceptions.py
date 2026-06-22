"""Domain exception hierarchy for Dax Assistant."""


class DaxError(Exception):
    """Base exception for all Dax errors."""


class ConfigError(DaxError):
    """Configuration loading or validation failed."""


class LLMError(DaxError):
    """LLM provider communication failed."""


class LLMTimeoutError(LLMError):
    """LLM request timed out."""


class LLMProviderUnavailableError(LLMError):
    """No LLM provider is available to handle the request."""


class ToolError(DaxError):
    """MCP tool execution failed."""


class ToolNotFoundError(ToolError):
    """Requested tool does not exist in the registry."""


class ToolExecutionError(ToolError):
    """Tool was found but execution failed."""


class ChannelError(DaxError):
    """Channel communication failed."""


class StorageError(DaxError):
    """Database or persistence operation failed."""


class VoiceError(DaxError):
    """Voice pipeline component failed."""


class WakeWordError(VoiceError):
    """Wake word detection failed."""


class STTError(VoiceError):
    """Speech-to-text transcription failed."""


class TTSError(VoiceError):
    """Text-to-speech synthesis failed."""
