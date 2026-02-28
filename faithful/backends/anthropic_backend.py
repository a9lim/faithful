from __future__ import annotations

from typing import TYPE_CHECKING

import anthropic

from .llm import BaseLLMBackend

if TYPE_CHECKING:
    from faithful.config import Config


class AnthropicBackend(BaseLLMBackend):
    """Generates text via the Anthropic Messages API."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)

    @staticmethod
    def _normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Ensure messages alternate user/assistant and don't start with assistant.

        Anthropic requires strict role alternation. Consecutive same-role messages
        are merged, and leading assistant messages are dropped.
        """
        # Drop leading assistant messages
        start = 0
        for i, msg in enumerate(messages):
            if msg["role"] != "assistant":
                start = i
                break
        else:
            # All messages are assistant — return a single fallback user message
            return [{"role": "user", "content": "(Send a casual message to the channel.)"}]

        trimmed = messages[start:]

        # Merge consecutive same-role messages
        merged: list[dict[str, str]] = []
        for msg in trimmed:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1] = {
                    "role": msg["role"],
                    "content": merged[-1]["content"] + "\n" + msg["content"],
                }
            else:
                merged.append(dict(msg))

        return merged if merged else [{"role": "user", "content": "(Send a casual message to the channel.)"}]

    async def _call_api(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        normalized = self._normalize_messages(messages)
        message = await self._client.messages.create(
            model=self.config.anthropic_model,
            max_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature,
            system=system_prompt,
            messages=normalized,
        )
        return (message.content[0].text or "").strip()
