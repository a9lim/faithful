from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from .base import Attachment
from .llm import BaseLLMBackend

if TYPE_CHECKING:
    from faithful.config import Config
    from faithful.tools import ToolCall

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIBackend(BaseLLMBackend):
    """Generates text via the OpenAI Responses API."""

    _has_native_search = True

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._client = AsyncOpenAI(api_key=config.api_key)

    def _build_input(
        self,
        system_prompt: str,
        messages: list[Any],
        attachments: list[Attachment] | None = None,
    ) -> list[dict[str, Any]]:
        input_messages: list[dict[str, Any]] = [
            {"role": "developer", "content": system_prompt},
            *messages,
        ]
        if attachments:
            last = input_messages[-1]
            content: list[dict[str, Any]] = [
                {"type": "input_text", "text": last.get("content", "")},
            ]
            for att in attachments:
                b64 = base64.b64encode(att.data).decode()
                content.append({
                    "type": "input_image",
                    "image_url": f"data:{att.content_type};base64,{b64}",
                })
            input_messages[-1] = {"role": last["role"], "content": content}
        return input_messages

    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        input_messages = self._build_input(system_prompt, messages, attachments)

        tools: list[dict[str, Any]] | None = None
        if self.config.enable_web_search:
            tools = [{"type": "web_search_preview"}]

        response = await self._client.responses.create(
            model=self.config.model or DEFAULT_MODEL,
            input=input_messages,
            max_output_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **({"tools": tools} if tools else {}),
        )
        return (response.output_text or "").strip()

    # ── Tool support ─────────────────────────────────────

    def _format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formatted = [
            {"type": "function", "name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in tools
        ]
        if self.config.enable_web_search:
            formatted.insert(0, {"type": "web_search_preview"})
        return formatted

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        from faithful.tools import ToolCall as TC

        input_messages = self._build_input(system_prompt, messages, attachments)

        response = await self._client.responses.create(
            model=self.config.model or DEFAULT_MODEL,
            input=input_messages,
            tools=tools,
            max_output_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        text = None
        tool_calls: list[ToolCall] = []

        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        text = part.text
            elif item.type == "function_call":
                try:
                    args = json.loads(item.arguments) if item.arguments else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(TC(id=item.call_id, name=item.name, arguments=args))
            # web_search_call is handled server-side — ignore it

        return text, tool_calls

    def _append_tool_result(
        self,
        messages: list[Any],
        call: ToolCall,
        result: str,
    ) -> list[Any]:
        messages = list(messages)
        messages.append({
            "type": "function_call",
            "call_id": call.id,
            "name": call.name,
            "arguments": json.dumps(call.arguments),
        })
        messages.append({
            "type": "function_call_output",
            "call_id": call.id,
            "output": result,
        })
        return messages
