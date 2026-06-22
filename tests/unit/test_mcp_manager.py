"""Tests for MCP manager env var resolution and transport selection."""

from __future__ import annotations

import os
from unittest.mock import patch

from dax.mcp.manager import _resolve_env_dict, _resolve_env_vars


class TestEnvVarResolution:
    def test_no_pattern(self):
        assert _resolve_env_vars("plain text") == "plain text"

    def test_single_env_var(self):
        with patch.dict(os.environ, {"MY_API_KEY": "secret123"}):
            result = _resolve_env_vars("{env:MY_API_KEY}")
            assert result == "secret123"

    def test_env_var_in_url(self):
        with patch.dict(os.environ, {"HA_TOKEN": "abc"}):
            result = _resolve_env_vars("Bearer {env:HA_TOKEN}")
            assert result == "Bearer abc"

    def test_multiple_env_vars(self):
        with patch.dict(os.environ, {"USER": "dax", "HOST": "local"}):
            result = _resolve_env_vars("{env:USER}@{env:HOST}")
            assert result == "dax@local"

    def test_missing_env_var_returns_empty(self):
        result = _resolve_env_vars("{env:NONEXISTENT_VAR_12345}")
        assert result == ""

    def test_resolve_dict(self):
        with patch.dict(os.environ, {"KEY": "value"}):
            result = _resolve_env_dict({
                "plain": "no change",
                "secret": "{env:KEY}",
            })
            assert result == {"plain": "no change", "secret": "value"}
