from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

import markovify

from .base import Backend, GenerationRequest

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
        text = "\n".join(examples)
        loop = asyncio.get_running_loop()
        self._model = await loop.run_in_executor(
            None,
            lambda: markovify.NewlineText(text, well_formed=False, state_size=2),
        )

    async def generate(self, request: GenerationRequest) -> str:
        if self._model is None:
            return "I don't have any example messages to work with yet."

        sentences: list[str] = []
        target = random.randint(1, 3)
        for _ in range(target * 5):
            s = self._model.make_sentence(tries=100)
            if s:
                sentences.append(s)
            if len(sentences) >= target:
                break

        if not sentences:
            s = self._model.make_short_sentence(280, tries=100)
            if s:
                sentences.append(s)

        return " ".join(sentences) if sentences else "..."
