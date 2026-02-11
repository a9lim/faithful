"""Base class for LLM-based text-generation backends."""

from __future__ import annotations

import random
from abc import abstractmethod
from typing import TYPE_CHECKING

from .base import Backend

if TYPE_CHECKING:
    from faithy.config import Config


class BaseLLMBackend(Backend):
    """Common logic for backends using a Chat Completions-style API."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._all_examples: list[str] = []

    async def setup(self, examples: list[str]) -> None:
        self._all_examples = examples

    @abstractmethod
    async def _call_api(self, messages: list[dict[str, str]]) -> str:
        """Call the specific model API."""

    async def generate(
        self,
        prompt: str,
        examples: str,
        recent_context: list[dict[str, str]],
    ) -> str:
        # Dynamic sampling
        if len(self._all_examples) > self.config.llm_sample_size:
            selected = random.sample(self._all_examples, self.config.llm_sample_size)
        else:
            selected = self._all_examples

        # Build system prompt
        text_examples = "\n".join(selected)
        system_prompt = self.config.system_prompt_template.format(
            name=self.config.persona_name,
            examples=text_examples
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Add context from channel
        messages.extend(recent_context)

        # Add the triggering message
        if prompt:
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append(
                {"role": "user", "content": "(Send a casual message to the channel.)"}
            )

        return await self._call_api(messages)
