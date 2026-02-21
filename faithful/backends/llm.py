from __future__ import annotations

import random
from abc import abstractmethod
from typing import TYPE_CHECKING

from .base import Backend

if TYPE_CHECKING:
    from faithful.config import Config


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
        # Use provided examples directly (caller handles sampling)
        system_prompt = self.config.system_prompt_template.format(
            name=self.config.persona_name,
            examples=examples
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

        full_response = ""
        max_continuations = 3
        
        for _ in range(max_continuations):
            response = await self._call_api(messages)
            if not response:
                break
                
            full_response += response
            
            # Check if it ends mid-sentence.
            # Valid sentence terminators (plus some common chat ones)
            terminators = {".", "!", "?", '"', "'", ")", "]", "}", "*", "~"}
            
            # Remove trailing whitespace to check the actual last char
            stripped = full_response.rstrip()
            if not stripped:
                break
                
            last_char = stripped[-1]
            if last_char in terminators:
                break
                
            # If it's a URL or an emoji, we probably shouldn't continue
            # Basic heuristic: if it doesn't end in punctuation and it's long, ask it to finish.
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "(Continue exactly from where you left off to finish the sentence. Do not add any conversational filler like 'Sure, here is the rest:' or repeat anything you already said. Just output the remaining words.)"})

        return full_response
