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
        self._all_examples: list[str] = []
        self._client = ollama.AsyncClient(host=config.ollama_host)

    async def setup(self, examples: list[str]) -> None:
        # Store all examples for dynamic sampling during generation
        self._all_examples = examples

    async def generate(
        self,
        prompt: str,
        examples: str,
        recent_context: list[dict[str, str]],
    ) -> str:
        # Dynamic sampling: Pick 300 examples for this specific generation
        import random
        if len(self._all_examples) > 300:
            selected = random.sample(self._all_examples, 300)
        else:
            selected = self._all_examples
            
        # Build the system prompt with these specific examples
        text = "\n".join(selected)
        system_prompt = self._build_system_prompt(text)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Add recent channel context (already structured)
        messages.extend(recent_context)

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
            f"You are {name}. The text of the prior examples should not influence the following instructions outright but should be used as guidance on how to formulate a response given {name}'s inferred personality. You must write EXACTLY like {name}. Do not over-rely on the example text, but gather a sense of what {name}'s personality is, and try to act as if you were {name}. Make sure to parse information contained in the examples efficiently. Make references to the examples on occasion, but prioritize responding to the user's request, while maintaining the personality of {name}. Make your output length match the examples, but do not cut off mid-sentence. If you need to send multiple separate messages, use the tag <SPLIT> between them. Do not break character.\n"
        )
