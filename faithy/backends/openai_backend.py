"""OpenAI-compatible backend — works with any API that speaks the OpenAI chat format."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from .base import Backend

if TYPE_CHECKING:
    from faithy.config import Config


class OpenAIBackend(Backend):
    """Generates text via an OpenAI-compatible chat completions API."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._system_prompt: str = ""
        self._client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )

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

        response = await self._client.chat.completions.create(
            model=self.config.openai_model,
            messages=messages,
            max_tokens=256,
            temperature=0.9,
        )
        return (response.choices[0].message.content or "").strip()

    def _build_system_prompt(self, examples: str) -> str:
        name = self.config.persona_name
        return (
            f"You are {name}. You must write EXACTLY like {name} — match the tone, "
            f"vocabulary, slang, punctuation, capitalization, emoji usage, and sentence "
            f"structure shown in the example messages below. Stay in character at all "
            f"times. Never mention that you are an AI or a bot. Keep responses concise "
            f"and natural — typically 1–3 sentences, matching the length of the examples.\n\n"
            f"### Example messages from {name}:\n"
            f"{examples}\n"
        )
