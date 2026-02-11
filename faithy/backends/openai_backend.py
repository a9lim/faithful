"""OpenAI-compatible backend — works with any API that speaks the OpenAI chat format."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from .base import Backend

from .llm import BaseLLMBackend

if TYPE_CHECKING:
    from faithy.config import Config


class OpenAIBackend(BaseLLMBackend):
    """Generates text via an OpenAI-compatible chat completions API."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )

    async def _call_api(self, messages: list[dict[str, str]]) -> str:
        response = await self._client.chat.completions.create(
            model=self.config.openai_model,
            messages=messages,
            max_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature,
        )
        return (response.choices[0].message.content or "").strip()
