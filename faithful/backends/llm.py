from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from .base import Backend, GenerationRequest

if TYPE_CHECKING:
    from faithful.config import Config


class BaseLLMBackend(Backend):
    """Common logic for backends using a chat-style API."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._all_examples: list[str] = []

    async def setup(self, examples: list[str]) -> None:
        self._all_examples = examples

    @abstractmethod
    async def _call_api(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """Call the specific model API. Each backend handles system_prompt placement."""

    def _build_system_prompt(self, request: GenerationRequest) -> str:
        """Format the system prompt template with persona name and examples."""
        examples_text = "\n".join(request.examples)
        return request.system_prompt_template.format(
            name=request.persona_name,
            examples=examples_text,
        )

    async def generate(self, request: GenerationRequest) -> str:
        system_prompt = self._build_system_prompt(request)

        messages: list[dict[str, str]] = list(request.context)

        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        else:
            messages.append(
                {"role": "user", "content": "(Send a casual message to the channel.)"}
            )

        return await self._call_api(system_prompt, messages)
