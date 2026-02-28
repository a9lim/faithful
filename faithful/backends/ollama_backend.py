from __future__ import annotations

from typing import TYPE_CHECKING

import ollama

from .llm import BaseLLMBackend

if TYPE_CHECKING:
    from faithful.config import Config


class OllamaBackend(BaseLLMBackend):
    """Generates text using a local LLM served by Ollama."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._client = ollama.AsyncClient(host=config.ollama_host)

    async def _call_api(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        response = await self._client.chat(
            model=self.config.ollama_model,
            messages=full_messages,
            options={
                "temperature": self.config.llm_temperature,
                "num_predict": self.config.llm_max_tokens,
            },
        )
        return response["message"]["content"].strip()
