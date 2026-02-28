from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from .llm import BaseLLMBackend

if TYPE_CHECKING:
    from faithful.config import Config


class OpenAIBackend(BaseLLMBackend):
    """Generates text via the OpenAI Responses API."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )

    async def _call_api(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        input_messages: list[dict[str, str]] = [
            {"role": "developer", "content": system_prompt},
            *messages,
        ]
        response = await self._client.responses.create(
            model=self.config.openai_model,
            input=input_messages,
            max_output_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature,
        )
        return (response.output_text or "").strip()
