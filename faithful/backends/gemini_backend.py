from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types

from .base import Attachment
from .llm import BaseLLMBackend

if TYPE_CHECKING:
    from faithful.config import Config
    from faithful.tools import ToolCall

DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiBackend(BaseLLMBackend):
    """Generates text via the Google Gemini API."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._client = genai.Client(api_key=config.api_key)

    @staticmethod
    def _to_contents(messages: list[Any]) -> list[dict[str, Any]]:
        """Convert messages to Gemini contents format, handling mixed types."""
        contents: list[dict[str, Any]] = []
        for msg in messages:
            if "parts" in msg:
                # Already in Gemini format
                contents.append(msg)
            else:
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        return contents

    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        contents = self._to_contents(messages)

        if attachments:
            last_parts = contents[-1]["parts"]
            for att in attachments:
                b64 = base64.b64encode(att.data).decode()
                last_parts.append({
                    "inline_data": {
                        "mime_type": att.content_type,
                        "data": b64,
                    },
                })

        response = await self._client.aio.models.generate_content(
            model=self.config.model or DEFAULT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
            ),
        )
        return (response.text or "").strip()

    # ── Tool support ─────────────────────────────────────

    def _format_tools(self, tools: list[dict[str, Any]]) -> list[types.Tool]:
        declarations = []
        for t in tools:
            declarations.append(types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"],
            ))
        return [types.Tool(function_declarations=declarations)]

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        from faithful.tools import ToolCall as TC

        contents = self._to_contents(messages)

        if attachments:
            last_parts = contents[-1]["parts"]
            for att in attachments:
                b64 = base64.b64encode(att.data).decode()
                last_parts.append({
                    "inline_data": {
                        "mime_type": att.content_type,
                        "data": b64,
                    },
                })

        response = await self._client.aio.models.generate_content(
            model=self.config.model or DEFAULT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
                tools=tools,
            ),
        )

        text_out = None
        tool_calls: list[ToolCall] = []

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text_out = part.text
                elif part.function_call:
                    fc = part.function_call
                    args = dict(fc.args) if fc.args else {}
                    tool_calls.append(TC(
                        id=fc.name,  # Gemini doesn't have separate call IDs
                        name=fc.name,
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
        # Model message with FunctionCall part
        messages.append({
            "role": "model",
            "parts": [types.Part.from_function_call(
                name=call.name,
                args=call.arguments,
            )],
        })
        # User message with FunctionResponse part
        try:
            result_dict = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            result_dict = {"result": result}
        messages.append({
            "role": "user",
            "parts": [types.Part.from_function_response(
                name=call.name,
                response=result_dict,
            )],
        })
        return messages
