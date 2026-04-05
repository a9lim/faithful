"""Tool system — definitions, memory executor, and dispatch."""

from faithful.tools.definitions import (
    TOOL_CONTINUE,
    TOOL_MEMORY,
    TOOL_WEB_FETCH,
    TOOL_WEB_SEARCH,
)
from faithful.tools.executor import ToolExecutor
from faithful.tools.memory import MemoryExecutor

# Re-export ToolCall for backward compatibility
from faithful.backends.base import ToolCall as ToolCall  # noqa: F401

__all__ = [
    "TOOL_CONTINUE",
    "TOOL_MEMORY",
    "TOOL_WEB_FETCH",
    "TOOL_WEB_SEARCH",
    "MemoryExecutor",
    "ToolCall",
    "ToolExecutor",
]
