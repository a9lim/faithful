from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faithful.config import Config


@dataclass(frozen=True)
class GenerationRequest:
    """Everything a backend needs to produce a response."""

    prompt: str
    system_prompt: str
    context: list[dict[str, str]] = field(default_factory=list)


class Backend(ABC):
    """Interface that every text-generation backend must implement."""

    def __init__(self, config: Config) -> None:
        self.config = config

    @abstractmethod
    async def setup(self, examples: list[str]) -> None:
        """Called when the example corpus changes (or on first load)."""

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> str:
        """Generate a response from a GenerationRequest."""
