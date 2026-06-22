"""Tests for core domain models."""

from __future__ import annotations

from dax.core.models import (
    ChannelType,
    Conversation,
    Language,
    Message,
    MessageRole,
    ToolCall,
    ToolResult,
)


class TestMessage:
    def test_default_values(self):
        msg = Message()
        assert msg.role == MessageRole.USER
        assert msg.content == ""
        assert msg.channel == ChannelType.WEB
        assert msg.language == Language.AUTO
        assert msg.id  # Should have a UUID
        assert msg.timestamp.tzinfo is not None

    def test_custom_values(self):
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Hello there",
            channel=ChannelType.VOICE,
            language=Language.SPANISH,
        )
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hello there"
        assert msg.channel == ChannelType.VOICE
        assert msg.language == Language.SPANISH

    def test_immutability(self):
        msg = Message(content="test")
        # frozen=True should prevent attribute assignment
        try:
            msg.content = "changed"  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass

    def test_unique_ids(self):
        msg1 = Message()
        msg2 = Message()
        assert msg1.id != msg2.id

    def test_with_tool_calls(self):
        call = ToolCall(
            id="call-1",
            server_name="shell",
            tool_name="execute",
            arguments={"command": "date"},
        )
        msg = Message(tool_calls=(call,))
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].tool_name == "execute"

    def test_with_tool_results(self):
        result = ToolResult(call_id="call-1", content="Thu Mar 19 12:00:00 UTC 2026")
        msg = Message(tool_results=(result,))
        assert len(msg.tool_results) == 1
        assert not msg.tool_results[0].is_error


class TestToolCall:
    def test_creation(self):
        call = ToolCall(
            id="tc-1",
            server_name="spotify",
            tool_name="play",
            arguments={"track": "bohemian rhapsody"},
        )
        assert call.server_name == "spotify"
        assert call.arguments["track"] == "bohemian rhapsody"


class TestToolResult:
    def test_success(self):
        result = ToolResult(call_id="tc-1", content="Playing now")
        assert not result.is_error

    def test_error(self):
        result = ToolResult(call_id="tc-1", content="Track not found", is_error=True)
        assert result.is_error


class TestConversation:
    def test_empty_conversation(self):
        conv = Conversation()
        assert conv.message_count == 0
        assert conv.last_message is None

    def test_add_message(self):
        conv = Conversation(channel=ChannelType.VOICE)
        msg = Message(content="Hello", channel=ChannelType.VOICE)
        initial_updated = conv.updated_at

        conv.add_message(msg)

        assert conv.message_count == 1
        assert conv.last_message is msg
        assert conv.updated_at >= initial_updated

    def test_multiple_messages(self):
        conv = Conversation()
        for i in range(5):
            conv.add_message(Message(content=f"Message {i}"))

        assert conv.message_count == 5
        assert conv.last_message is not None
        assert conv.last_message.content == "Message 4"

    def test_unique_ids(self):
        conv1 = Conversation()
        conv2 = Conversation()
        assert conv1.id != conv2.id


class TestEnums:
    def test_channel_type_values(self):
        assert ChannelType.VOICE == "voice"
        assert ChannelType.WHATSAPP == "whatsapp"
        assert ChannelType.WEB == "web"

    def test_message_role_values(self):
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.SYSTEM == "system"
        assert MessageRole.TOOL == "tool"

    def test_language_values(self):
        assert Language.SPANISH == "es"
        assert Language.ENGLISH == "en"
        assert Language.AUTO == "auto"
