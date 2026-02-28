from __future__ import annotations

from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from .llm import BaseLLMBackend

if TYPE_CHECKING:
    from faithful.config import Config


class GeminiBackend(BaseLLMBackend):
    """Generates text via the Google Gemini API."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._client = genai.Client(api_key=config.gemini_api_key)

    async def _call_api(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        # Gemini uses "model" instead of "assistant"
        contents: list[dict[str, str]] = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = await self._client.aio.models.generate_content(
            model=self.config.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.config.llm_temperature,
                max_output_tokens=self.config.llm_max_tokens,
            ),
        )
        return (response.text or "").strip()
