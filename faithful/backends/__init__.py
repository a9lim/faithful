from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faithful.config import Config
    from .base import Backend

log = logging.getLogger("faithful.backends")

# Map of backend names to (module_path, class_name, required_package)
_BACKEND_REGISTRY: dict[str, tuple[str, str, str]] = {
    "openai": ("faithful.backends.openai", "OpenAIBackend", "openai"),
    "openai-compatible": ("faithful.backends.openai_compat", "OpenAICompatibleBackend", "openai"),
    "gemini": ("faithful.backends.gemini", "GeminiBackend", "google.genai"),
    "anthropic": ("faithful.backends.anthropic", "AnthropicBackend", "anthropic"),
}

BACKEND_NAMES = list(_BACKEND_REGISTRY.keys())


def get_backend(name: str, config: Config) -> Backend:
    """Instantiate and return a backend by name.

    Backend SDK dependencies are imported lazily — only the active backend's
    package needs to be installed. A clear error is raised if it's missing.
    """
    entry = _BACKEND_REGISTRY.get(name.lower())
    if entry is None:
        raise ValueError(
            f"Unknown backend '{name}'. Choose from: {', '.join(_BACKEND_REGISTRY)}"
        )

    module_path, class_name, package = entry
    try:
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
    except ImportError as e:
        raise ImportError(
            f"Backend '{name}' requires the '{package}' package. "
            f"Install it with: pip install {package}\n"
            f"Original error: {e}"
        ) from e

    return cls(config)
