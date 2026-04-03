"""Tests for faithful.prompt — system prompt formatting."""

from __future__ import annotations

from faithful.prompt import format_system_prompt


class TestFormatSystemPrompt:
    def test_basic_formatting(self):
        result = format_system_prompt(
            template="Hello {name}, examples: {examples}, emojis: {custom_emojis}",
            persona_name="TestBot",
            examples=["msg1", "msg2"],
            custom_emojis="none",
        )
        assert "TestBot" in result
        assert "msg1\nmsg2" in result
        assert "none" in result

    def test_memory_protocol_injected_for_non_native(self):
        result = format_system_prompt(
            template="{name}{examples}{custom_emojis}",
            persona_name="bot",
            examples=[],
            enable_memory=True,
            has_native_memory=False,
        )
        assert "MEMORY PROTOCOL" in result

    def test_no_memory_protocol_for_native(self):
        result = format_system_prompt(
            template="{name}{examples}{custom_emojis}",
            persona_name="bot",
            examples=[],
            enable_memory=True,
            has_native_memory=True,
        )
        assert "MEMORY PROTOCOL" not in result

    def test_no_memory_protocol_when_disabled(self):
        result = format_system_prompt(
            template="{name}{examples}{custom_emojis}",
            persona_name="bot",
            examples=[],
            enable_memory=False,
        )
        assert "MEMORY PROTOCOL" not in result
