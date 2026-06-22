"""Tests for the tool execution policy."""

from __future__ import annotations

from dax.core.config import ToolPolicyConfig
from dax.core.policy import Decision, ToolPolicy


class TestToolPolicy:
    def test_defaults_gate_destructive(self):
        p = ToolPolicy()
        assert p.decide("fs_write") == Decision.ASK
        assert p.decide("shell_run") == Decision.ASK
        assert p.decide("open_path") == Decision.ASK
        assert p.decide("clipboard_set") == Decision.ASK

    def test_defaults_allow_readonly(self):
        p = ToolPolicy()
        assert p.decide("fs_read") == Decision.ALLOW
        assert p.decide("system_info") == Decision.ALLOW
        assert p.decide("fs_list") == Decision.ALLOW

    def test_deny_wins_over_everything(self):
        p = ToolPolicy(deny=["fs_*"], ask=["fs_write"], allow=["fs_read"])
        assert p.decide("fs_read") == Decision.DENY
        assert p.decide("fs_write") == Decision.DENY

    def test_explicit_allow_over_default(self):
        p = ToolPolicy(default=Decision.DENY, ask=[], allow=["custom_tool"])
        assert p.decide("custom_tool") == Decision.ALLOW
        assert p.decide("anything_else") == Decision.DENY

    def test_case_insensitive(self):
        p = ToolPolicy(ask=["*WRITE*"])
        assert p.decide("fs_write") == Decision.ASK

    def test_from_config_empty_ask_uses_defaults(self):
        p = ToolPolicy.from_config(ToolPolicyConfig())
        assert p.decide("shell_run") == Decision.ASK
        assert p.decide("fs_read") == Decision.ALLOW

    def test_from_config_custom(self):
        cfg = ToolPolicyConfig(default="deny", ask=["*danger*"], allow=["safe_*"])
        p = ToolPolicy.from_config(cfg)
        assert p.decide("safe_op") == Decision.ALLOW
        assert p.decide("do_danger") == Decision.ASK
        assert p.decide("unknown") == Decision.DENY
