from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

import ollama

from .base import Attachment, Backend, ToolCall

if TYPE_CHECKING:
    from faithful.config import Config

DEFAULT_MODEL = "llama3"
DEFAULT_HOST = "http://localhost:11434"


class OllamaBackend(Backend):
    """Generates text using a local LLM served by Ollama."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._client = ollama.AsyncClient(host=config.host or DEFAULT_HOST)

    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        full_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        if attachments:
            last = full_messages[-1]
            last["images"] = [
                base64.b64encode(att.data).decode() for att in attachments
            ]

        response = await self._client.chat(
            model=self.config.model or DEFAULT_MODEL,
            messages=full_messages,
            options={
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        )
        return response["message"]["content"].strip()

    # ── Tool support ─────────────────────────────────────

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
        full_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        if attachments:
            last = full_messages[-1]
            last["images"] = [
                base64.b64encode(att.data).decode() for att in attachments
            ]

        response = await self._client.chat(
            model=self.config.model or DEFAULT_MODEL,
            messages=full_messages,
            tools=tools,
            options={
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        )

        msg = response["message"]
        text_out = msg.get("content") or None
        tool_calls: list[ToolCall] = []

        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            tool_calls.append(ToolCall(
                id=func.get("name", ""),
                name=func.get("name", ""),
                arguments=args,
            ))

        return text_out, tool_calls

    def _append_tool_result(
        self,
        messages: list[Any],
        call: ToolCall,
        result: str,
    ) -> list[Any]:
        messages = list(messages)
        messages.append({"role": "tool", "content": result})
        return messages
