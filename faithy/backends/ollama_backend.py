"""Ollama backend — uses a locally-hosted LLM via the Ollama API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ollama

from .base import Backend

if TYPE_CHECKING:
    from faithy.config import Config


class OllamaBackend(Backend):
    """Generates text using a local LLM served by Ollama."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._system_prompt: str = ""
        self._client = ollama.AsyncClient(host=config.ollama_host)

    async def setup(self, examples: str) -> None:
        self._system_prompt = self._build_system_prompt(examples)

    async def generate(
        self,
        prompt: str,
        examples: str,
        recent_context: list[str],
    ) -> str:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]

        # Add recent channel context
        for msg in recent_context:
            messages.append({"role": "user", "content": msg})

        # Add the triggering message (or a nudge for spontaneous messages)
        if prompt:
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append(
                {"role": "user", "content": "(Send a casual message to the channel.)"}
            )

        response = await self._client.chat(
            model=self.config.ollama_model,
            messages=messages,
        )
        return response["message"]["content"].strip()

    def _build_system_prompt(self, examples: str) -> str:
        name = self.config.persona_name
        return (
            f"### Example messages from {name}:\n"
            f"{examples}\n"
        )
