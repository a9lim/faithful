from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from .base import Attachment, Backend, ToolCall

if TYPE_CHECKING:
    from faithful.config import Config

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAICompatibleBackend(Backend):
    """Generates text via the OpenAI-compatible Chat Completions API.

    Works with any provider that implements ``/v1/chat/completions``
    (LM Studio, vLLM, text-generation-webui, etc.).
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        if not config.base_url:
            raise ValueError(
                "openai-compatible backend requires 'base_url' in [backend] config"
            )
        self._client = AsyncOpenAI(
            api_key=config.api_key or "not-needed",
            base_url=config.base_url,
        )

    def _build_messages(
        self,
        system_prompt: str,
        messages: list[Any],
        attachments: list[Attachment] | None = None,
    ) -> list[dict[str, Any]]:
        full: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]
        if attachments:
            last = full[-1]
            content: list[dict[str, Any]] = [
                {"type": "text", "text": last.get("content", "")},
            ]
            for att in attachments:
                b64 = att.b64
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{att.content_type};base64,{b64}"},
                })
            full[-1] = {"role": last["role"], "content": content}
        return full

    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        full = self._build_messages(system_prompt, messages, attachments)

        response = await self._client.chat.completions.create(
            model=self.config.model or DEFAULT_MODEL,
            messages=full,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        return (response.choices[0].message.content or "").strip()

    # -- Tool support --------------------------------------------------

    def _format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        full = self._build_messages(system_prompt, messages, attachments)

        response = await self._client.chat.completions.create(
            model=self.config.model or DEFAULT_MODEL,
            messages=full,
            tools=tools,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        msg = response.choices[0].message
        text = msg.content or None
        tool_calls: list[ToolCall] = []

        for tc in msg.tool_calls or []:
            args = self._parse_json_args(tc.function.arguments)
            tool_calls.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            ))

        return text, tool_calls

    def _append_tool_result(
        self,
        messages: list[Any],
        call: ToolCall,
        result: str,
    ) -> list[Any]:
        messages = list(messages)
        messages.append({
            "role": "assistant",
            "tool_calls": [{
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": result,
        })
        return messages
