from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anthropic

from .base import Attachment, Backend, SPONTANEOUS_PROMPT, ToolCall

if TYPE_CHECKING:
    from faithful.config import Config

DEFAULT_MODEL = "claude-sonnet-4-20250514"

MAX_PAUSE_TURNS = 10


class AnthropicBackend(Backend):
    """Generates text via the Anthropic Messages API."""

    _has_native_server_tools = True
    _has_native_memory = True

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._client = anthropic.AsyncAnthropic(api_key=config.api_key)

    @staticmethod
    def _normalize_messages(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Ensure strict user/assistant alternation required by the Anthropic API.

        Messages with list content (compacted blocks, tool blocks) are passed
        through unchanged — they must not be string-concatenated.
        """
        start = 0
        for i, msg in enumerate(messages):
            if msg["role"] != "assistant":
                start = i
                break
        else:
            return [{"role": "user", "content": SPONTANEOUS_PROMPT}]

        merged: list[dict[str, Any]] = []
        for msg in messages[start:]:
            # Skip synthetic tool_results role — handled by _append_tool_result
            if msg.get("role") == "tool_results":
                continue

            if merged and merged[-1]["role"] == msg["role"]:
                prev_content = merged[-1]["content"]
                curr_content = msg.get("content", "")

                # Only merge plain strings; lists (compacted/tool blocks) pass through
                if isinstance(prev_content, str) and isinstance(curr_content, str):
                    merged[-1] = {
                        "role": msg["role"],
                        "content": prev_content + "\n" + curr_content,
                    }
                else:
                    merged.append(dict(msg))
            else:
                merged.append(dict(msg))

        return merged or [{"role": "user", "content": SPONTANEOUS_PROMPT}]

    @staticmethod
    def _extract_text(content: list[Any]) -> str:
        """Extract text from response content blocks, skipping server tool blocks."""
        parts: list[str] = []
        for block in content:
            if getattr(block, "type", None) == "text" and hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts).strip()

    def _apply_attachments(
        self,
        normalized: list[dict[str, Any]],
        attachments: list[Attachment] | None,
    ) -> list[dict[str, Any]]:
        if not attachments:
            return normalized
        last = normalized[-1]
        text = last["content"] if isinstance(last["content"], str) else ""
        content: list[dict[str, Any]] = []
        for att in attachments:
            b64 = att.b64
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": att.content_type,
                    "data": b64,
                },
            })
        content.append({"type": "text", "text": text})
        normalized[-1] = {"role": last["role"], "content": content}
        return normalized

    def _native_server_tools(self) -> list[dict[str, Any]]:
        """Return Anthropic server-side tools enabled by config."""
        tools: list[dict[str, Any]] = []
        if self.config.enable_web_search:
            tools.append({"type": "web_search_20260209", "name": "web_search", "max_uses": 3})
            tools.append({"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3})
            tools.append({"type": "code_execution_20260120", "name": "code_execution"})
        return tools

    def _native_memory_tool(self) -> list[dict[str, Any]]:
        """Return the Anthropic memory tool if enabled."""
        if self.config.enable_memory:
            return [{"type": "memory_20250818", "name": "memory"}]
        return []

    def _beta_headers(self) -> list[str]:
        """Build list of Anthropic beta header strings from config."""
        betas: list[str] = []
        if self.config.enable_1m_context:
            betas.append("context-1m-2025-08-07")
        if self.config.enable_compaction:
            betas.append("compact-2026-01-12")
        return betas

    def _build_kwargs(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build kwargs dict shared by _call_api and _call_with_tools."""
        kwargs: dict[str, Any] = {
            "model": self.config.model or DEFAULT_MODEL,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": [{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if self.config.enable_thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        if self.config.enable_compaction:
            kwargs["context_management"] = {
                "edits": [{"type": "compact_20260112"}]
            }
        betas = self._beta_headers()
        if betas:
            kwargs["betas"] = betas
        return kwargs

    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        normalized = self._normalize_messages(messages)
        normalized = self._apply_attachments(normalized, attachments)

        tools = self._native_server_tools() + self._native_memory_tool()
        kwargs = self._build_kwargs(system_prompt, normalized, tools or None)

        async with self._client.beta.messages.stream(**kwargs) as stream:
            message = await stream.get_final_message()

        # Handle pause_turn for server-side tool loops
        for _ in range(MAX_PAUSE_TURNS):
            if message.stop_reason != "pause_turn":
                break
            normalized.append({"role": "assistant", "content": message.content})
            kwargs["messages"] = normalized
            async with self._client.beta.messages.stream(**kwargs) as stream:
                message = await stream.get_final_message()

        return self._extract_text(message.content)

    # ── Tool support ─────────────────────────────────────

    def _format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Format client-side tools (continue)
        formatted = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]
        # Prepend native server tools + memory tool
        formatted = self._native_server_tools() + self._native_memory_tool() + formatted
        return formatted

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        normalized = self._normalize_messages(messages)
        normalized = self._apply_attachments(normalized, attachments)

        kwargs = self._build_kwargs(system_prompt, normalized, tools)

        async with self._client.beta.messages.stream(**kwargs) as stream:
            message = await stream.get_final_message()

        # Handle pause_turn for server-side tool loops
        for _ in range(MAX_PAUSE_TURNS):
            if message.stop_reason != "pause_turn":
                break
            normalized.append({"role": "assistant", "content": message.content})
            kwargs["messages"] = normalized
            async with self._client.beta.messages.stream(**kwargs) as stream:
                message = await stream.get_final_message()

        text_out = self._extract_text(message.content) or None
        tool_calls: list[ToolCall] = []

        for block in message.content:
            # Only handle client-side tool_use, not server_tool_use
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        return text_out, tool_calls

    def _append_tool_result(
        self,
        messages: list[Any],
        call: ToolCall,
        result: str,
    ) -> list[Any]:
        messages = list(messages)
        messages.append({
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
            ],
        })
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result,
                }
            ],
        })
        return messages
