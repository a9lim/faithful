from __future__ import annotations

from abc import abstractmethod

from .base import Backend, GenerationRequest


class BaseLLMBackend(Backend):
    """Common logic for backends that call a chat-style LLM API.

    Subclasses only implement ``_call_api`` to handle provider-specific
    API differences.
    """

    async def setup(self, examples: list[str]) -> None:
        pass  # LLM backends don't need pre-processing

    @abstractmethod
    async def _call_api(
        self, system_prompt: str, messages: list[dict[str, str]]
    ) -> str:
        """Send messages to the provider and return the response text."""

    async def generate(self, request: GenerationRequest) -> str:
        messages: list[dict[str, str]] = list(request.context)

        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        else:
            messages.append(
                {"role": "user", "content": "(Send a casual message to the channel.)"}
            )

        return await self._call_api(request.system_prompt, messages)
