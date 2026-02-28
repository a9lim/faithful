from __future__ import annotations

from typing import TYPE_CHECKING

from .anthropic_backend import AnthropicBackend
from .gemini_backend import GeminiBackend
from .markov import MarkovBackend
from .ollama_backend import OllamaBackend
from .openai_backend import OpenAIBackend

if TYPE_CHECKING:
    from faithful.config import Config
    from .base import Backend

_BACKENDS: dict[str, type[Backend]] = {
    "markov": MarkovBackend,
    "ollama": OllamaBackend,
    "openai": OpenAIBackend,
    "gemini": GeminiBackend,
    "anthropic": AnthropicBackend,
}

BACKEND_NAMES = list(_BACKENDS.keys())


def get_backend(name: str, config: Config) -> Backend:
    """Instantiate and return a backend by name."""
    cls = _BACKENDS.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown backend '{name}'. Choose from: {', '.join(_BACKENDS)}"
        )
    return cls(config)
