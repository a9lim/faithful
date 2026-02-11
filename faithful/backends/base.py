from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faithful.config import Config


class Backend(ABC):
    """Interface that every text-generation backend must implement."""

    def __init__(self, config: "Config") -> None:
        self.config = config

    @abstractmethod
    async def setup(self, examples: list[str]) -> None:
        """Called when the example corpus changes (or on first load).

        Backends should use this to rebuild any internal models or prompts
        from the raw example text.
        """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        examples: str,
        recent_context: list[dict[str, str]],
    ) -> str:
        """Generate a response.

        Args:
            prompt: The triggering message text (may be empty for
                    unprompted/spontaneous messages).
            examples: The full example-message corpus.
            recent_context: The last N messages in the channel for context.

        Returns:
            The generated response string.
        """
