from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from openai import AsyncOpenAI

from .base import Attachment, Backend, ToolCall

if TYPE_CHECKING:
    from faithful.config import Config

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIBackend(Backend):
    """Generates text via the OpenAI Responses API."""

    _has_native_server_tools = True

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._client = AsyncOpenAI(api_key=config.backend.api_key)

    def _build_input(
        self,
        system_prompt: str,
        messages: list[Any],
        attachments: list[Attachment] | None = None,
    ) -> list[dict[str, Any]]:
        input_messages: list[dict[str, Any]] = [
            {"role": "developer", "content": system_prompt},
        ]
        for msg in messages:
            # Skip provider-agnostic tool round entries from session history;
            # the tool loop builds provider-specific format via _append_tool_result
            if msg.get("role") == "tool_results" or "tool_calls" in msg:
                continue
            input_messages.append(msg)

        if attachments:
            last = input_messages[-1]
            content: list[dict[str, Any]] = [
                {"type": "input_text", "text": last.get("content", "")},
            ]
            for att in attachments:
                b64 = att.b64
                content.append({
                    "type": "input_image",
                    "image_url": f"data:{att.media_type};base64,{b64}",
                })
            input_messages[-1] = {"role": last["role"], "content": content}
        return input_messages

    def _native_server_tools(self) -> list[dict[str, Any]]:
        """Return native OpenAI server-side tools enabled by config.

        ``web_search`` is the current recommended grounding tool and (unlike
        the legacy ``web_search_preview``) supports domain filters and source
        annotations. ``code_interpreter`` adds a hosted Python sandbox for
        parity with Anthropic's ``code_execution`` and Gemini's
        ``ToolCodeExecution`` -- it doubles as a way for the model to fetch
        and parse arbitrary URLs that ``web_search`` may not surface.
        """
        if not self.config.behavior.enable_web_search:
            return []
        return [
            {"type": "web_search"},
            {"type": "code_interpreter", "container": {"type": "auto"}},
        ]

    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        input_messages = self._build_input(system_prompt, messages, attachments)
        tools = self._native_server_tools()

        # The Responses API expects a tightly-typed ResponseInputParam list
        # (a union of TypedDicts), but our message dicts are loose at the
        # boundary. Cast through Any so pyright doesn't flag the runtime-fine
        # dict shapes; the OpenAI client validates structure server-side.
        kwargs: dict[str, Any] = {
            "model": self.config.backend.model or DEFAULT_MODEL,
            "input": cast(Any, input_messages),
            "max_output_tokens": self.config.llm.max_tokens,
            "temperature": self.config.llm.temperature,
        }
        if tools:
            kwargs["tools"] = cast(Any, tools)

        response = await self._client.responses.create(**kwargs)
        return (response.output_text or "").strip()

    # ── Tool support ─────────────────────────────────────

    def _format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formatted = [
            {"type": "function", "name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in tools
        ]
        # Prepend native server tools (web_search, code_interpreter) so the
        # model sees them alongside our function tools.
        return self._native_server_tools() + formatted

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        input_messages = self._build_input(system_prompt, messages, attachments)

        response = await self._client.responses.create(
            model=self.config.backend.model or DEFAULT_MODEL,
            input=cast(Any, input_messages),
            tools=cast(Any, tools),
            max_output_tokens=self.config.llm.max_tokens,
            temperature=self.config.llm.temperature,
        )

        text: str | None = None
        tool_calls: list[ToolCall] = []

        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    # part is either ResponseOutputText (has .text) or
                    # ResponseOutputRefusal (has .refusal). Only output_text
                    # carries the assistant's spoken response.
                    if getattr(part, "type", None) == "output_text":
                        text = getattr(part, "text", None)
            elif item.type == "function_call":
                args = self._parse_json_args(item.arguments)
                tool_calls.append(ToolCall(id=item.call_id, name=item.name, arguments=args))
            # Server-side calls (web_search_call, code_interpreter_call, etc.)
            # are executed by OpenAI's infrastructure — they show up in
            # response.output but we don't need to act on them.

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
