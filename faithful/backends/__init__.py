from __future__ import annotations

from typing import TYPE_CHECKING

from .anthropic import AnthropicBackend
from .gemini import GeminiBackend
from .ollama import OllamaBackend
from .openai import OpenAIBackend
from .openai_compat import OpenAICompatibleBackend

if TYPE_CHECKING:
    from faithful.config import Config
    from .base import Backend

_BACKENDS: dict[str, type[Backend]] = {
    "ollama": OllamaBackend,
    "openai": OpenAIBackend,
    "openai-compatible": OpenAICompatibleBackend,
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
