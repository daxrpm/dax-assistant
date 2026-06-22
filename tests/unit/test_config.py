"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from dax.core.config import DaxConfig, load_config


class TestDaxConfig:
    def test_default_values(self):
        config = DaxConfig()
        assert config.name == "Dax"
        assert config.language_default == "es"
        assert config.log_level == "INFO"

    def test_voice_defaults(self):
        config = DaxConfig()
        assert config.voice.enabled is True
        assert config.voice.stt_model == "base"
        assert config.voice.stt_language == "auto"

    def test_llm_defaults(self):
        config = DaxConfig()
        assert config.llm.default_provider == "ollama"
        assert config.llm.ollama.model == "llama3.1:8b"
        assert config.llm.ollama.base_url == "http://localhost:11434"

    def test_web_defaults(self):
        config = DaxConfig()
        assert config.web.port == 8420
        # Loopback by default (personal assistant); LAN exposure is opt-in.
        assert config.web.host == "127.0.0.1"
        assert config.web.expose_lan is False
        assert config.web.effective_host == "127.0.0.1"

    def test_whatsapp_disabled_by_default(self):
        config = DaxConfig()
        assert config.whatsapp.enabled is False

    def test_storage_defaults(self):
        config = DaxConfig()
        assert config.storage.database_path == "data/dax.db"

    def test_mcp_empty_by_default(self):
        config = DaxConfig()
        assert config.mcp.servers == {}


class TestLoadConfig:
    def test_load_nonexistent_file(self):
        config = load_config(Path("/nonexistent/path.toml"))
        assert config.name == "Dax"  # Falls back to defaults

    def test_load_none_path(self):
        config = load_config(None)
        assert config.name == "Dax"

    def test_load_from_toml(self, tmp_path: Path):
        toml_content = """
[general]
name = "TestBot"
log_level = "DEBUG"

[llm.ollama]
model = "qwen3.5:4b"
timeout = 60
"""
        config_file = tmp_path / "test.toml"
        config_file.write_text(toml_content)

        config = load_config(config_file)
        assert config.name == "TestBot"
        assert config.log_level == "DEBUG"
        assert config.llm.ollama.model == "qwen3.5:4b"
        assert config.llm.ollama.timeout == 60

    def test_load_partial_overrides(self, tmp_path: Path):
        toml_content = """
[general]
name = "Partial"

[web]
port = 9999
"""
        config_file = tmp_path / "partial.toml"
        config_file.write_text(toml_content)

        config = load_config(config_file)
        assert config.name == "Partial"
        assert config.web.port == 9999
        # Other defaults preserved
        assert config.llm.default_provider == "ollama"
        assert config.voice.enabled is True
