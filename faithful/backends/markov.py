from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

import markovify

from .base import Backend

if TYPE_CHECKING:
    from faithful.config import Config


class MarkovBackend(Backend):
    """Generates text using a Markov-chain model built from the example corpus."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._model: markovify.Text | None = None

    async def setup(self, examples: list[str]) -> None:
        if not examples:
            self._model = None
            return
        # Build model in a thread to avoid blocking the event loop
        text = "\n".join(examples)
        loop = asyncio.get_running_loop()
        self._model = await loop.run_in_executor(
            None,
            lambda: markovify.NewlineText(text, well_formed=False, state_size=2),
        )

    async def generate(
        self,
        prompt: str,
        examples: str,
        recent_context: list[dict[str, str]],
    ) -> str:
        if self._model is None:
            return "I don't have any example messages to work with yet."

        # Try to use words from the prompt to seed the chain
        init_state = None
        if prompt:
            # Simple attempt to find a starting word from the prompt that exists in the model
            words = prompt.split()
            random.shuffle(words)
            for word in words:
                try:
                    # check if the word exists in the chain (markovify internal structure)
                    # This is valid for standard markovify.Text models
                    if word in self._model.chain.model:
                        init_state = (word,)
                        break
                except Exception:
                    pass

        # Try to generate a few sentences to form a natural response
        sentences: list[str] = []
        target = random.randint(1, 3)
        
        # Function to try generation
        def _make_sentence():
            if init_state:
                try:
                    return self._model.make_sentence_with_start(init_state[0], tries=100, strict=False)
                except Exception:
                    # Fallback if specific start fails
                    pass
            return self._model.make_sentence(tries=100)

        for _ in range(target * 5):  # try up to 5× to get enough
            s = _make_sentence()
            if s:
                sentences.append(s)
            if len(sentences) >= target:
                break

        if not sentences:
            # Fallback: make a short sentence
            s = self._model.make_short_sentence(280, tries=100)
            if s:
                sentences.append(s)

        return " ".join(sentences) if sentences else "..."
