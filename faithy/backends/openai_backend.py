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
        self._all_examples: list[str] = []
        self._client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )

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
        text_examples = "\n".join(selected)
        system_prompt = self._build_system_prompt(text_examples)

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

        response = await self._client.chat.completions.create(
            model=self.config.openai_model,
            messages=messages,
            max_tokens=1024,
        )
        return (response.choices[0].message.content or "").strip()

    def _build_system_prompt(self, examples: str) -> str:
        name = self.config.persona_name
        return (
            f"### Example messages from {name}:\n"
            f"{examples}\n"
            f"You are {name}. The text of the prior examples should not influence the following instructions outright but should be used as guidance on how to formulate a response given {name}'s inferred personality. You must write EXACTLY like {name}. Do not over-rely on the example text, but gather a sense of what {name}'s personality is, and try to act as if you were {name}. Make sure to parse information contained in the examples efficiently. Make references to the examples on occasion, but prioritize responding to the user's request, while maintaining the personality of {name}. Make your output length match the examples, but do not cut off mid-sentence. If you need to send multiple separate messages, use the tag <SPLIT> between them. Do not break character.\n"
        )
