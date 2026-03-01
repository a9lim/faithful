from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

import anthropic

from .base import Attachment
from .llm import SPONTANEOUS_PROMPT, BaseLLMBackend

if TYPE_CHECKING:
    from faithful.config import Config
    from faithful.tools import ToolCall

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class AnthropicBackend(BaseLLMBackend):
    """Generates text via the Anthropic Messages API."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._client = anthropic.AsyncAnthropic(api_key=config.api_key)

    @staticmethod
    def _normalize_messages(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Ensure strict user/assistant alternation required by the Anthropic API."""
        # Drop leading assistant messages
        start = 0
        for i, msg in enumerate(messages):
            if msg["role"] != "assistant":
                start = i
                break
        else:
            return [{"role": "user", "content": SPONTANEOUS_PROMPT}]

        # Merge consecutive same-role messages
        merged: list[dict[str, Any]] = []
        for msg in messages[start:]:
            if merged and merged[-1]["role"] == msg["role"]:
                prev_content = merged[-1]["content"]
                curr_content = msg["content"]
                # Only merge when both are plain strings
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

    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        normalized = self._normalize_messages(messages)

        if attachments:
            last = normalized[-1]
            text = last["content"] if isinstance(last["content"], str) else ""
            content: list[dict[str, Any]] = []
            for att in attachments:
                b64 = base64.b64encode(att.data).decode()
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

        message = await self._client.messages.create(
            model=self.config.model or DEFAULT_MODEL,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt,
            messages=normalized,
        )
        return (message.content[0].text or "").strip()

    # ── Tool support ─────────────────────────────────────

    def _format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        from faithful.tools import ToolCall as TC

        normalized = self._normalize_messages(messages)

        if attachments:
            last = normalized[-1]
            text = last["content"] if isinstance(last["content"], str) else ""
            content: list[dict[str, Any]] = []
            for att in attachments:
                b64 = base64.b64encode(att.data).decode()
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

        message = await self._client.messages.create(
            model=self.config.model or DEFAULT_MODEL,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt,
            messages=normalized,
            tools=tools,
        )

        text_out = None
        tool_calls: list[ToolCall] = []

        for block in message.content:
            if block.type == "text":
                text_out = block.text
            elif block.type == "tool_use":
                tool_calls.append(TC(
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
        # Append assistant message with tool_use block
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
        # Append user message with tool_result block
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
