"""Provider-agnostic tool definitions and executor."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from faithful.backends.base import ToolCall as ToolCall  # noqa: F401

if TYPE_CHECKING:
    from .memory import MemoryStore

log = logging.getLogger("faithful.tools")


# ── Provider-agnostic tool definitions ───────────────────

TOOL_WEB_SEARCH: dict[str, Any] = {
    "name": "web_search",
    "description": "Search the web for current information. Use when the conversation requires recent or factual information you're unsure about.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
        },
        "required": ["query"],
    },
}

TOOL_REMEMBER_USER: dict[str, Any] = {
    "name": "remember_user",
    "description": "Save a fact about a user for future conversations. Use when someone shares something memorable about themselves.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_name": {
                "type": "string",
                "description": "The display name of the user (as shown in the conversation).",
            },
            "fact": {
                "type": "string",
                "description": "The fact to remember about this user.",
            },
        },
        "required": ["user_name", "fact"],
    },
}

TOOL_REMEMBER_CHANNEL: dict[str, Any] = {
    "name": "remember_channel",
    "description": "Save a memory about this channel for future reference. Use for channel-specific context like ongoing topics or running jokes.",
    "parameters": {
        "type": "object",
        "properties": {
            "memory": {
                "type": "string",
                "description": "The thing to remember about this channel.",
            },
        },
        "required": ["memory"],
    },
}

ALL_TOOLS = [TOOL_WEB_SEARCH, TOOL_REMEMBER_USER, TOOL_REMEMBER_CHANNEL]


class ToolExecutor:
    """Executes tool calls, dispatching to the appropriate implementation."""

    def __init__(
        self,
        memory_store: MemoryStore | None,
        channel_id: int,
        participants: dict[int, str],
    ) -> None:
        self.memory_store = memory_store
        self.channel_id = channel_id
        self.participants = participants  # {user_id: display_name}

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool by name and return the result as a string."""
        try:
            if name == "web_search":
                return await self._web_search(args.get("query", ""))
            elif name == "remember_user":
                return self._remember_user(
                    args.get("user_name", ""), args.get("fact", "")
                )
            elif name == "remember_channel":
                return self._remember_channel(args.get("memory", ""))
            else:
                return json.dumps({"error": f"Unknown tool: {name}"})
        except Exception as e:
            log.exception("Tool '%s' failed.", name)
            return json.dumps({"error": str(e)})

    async def _web_search(self, query: str) -> str:
        if not query:
            return json.dumps({"error": "Empty search query."})
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return json.dumps({"error": "Web search unavailable (duckduckgo-search not installed)."})

        import asyncio
        import functools

        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None, functools.partial(DDGS().text, query, max_results=5)
            )
            if not results:
                return json.dumps({"results": [], "note": "No results found."})
            formatted = [
                {"title": r.get("title", ""), "body": r.get("body", ""), "url": r.get("href", "")}
                for r in results
            ]
            return json.dumps({"results": formatted})
        except Exception as e:
            return json.dumps({"error": f"Search failed: {e}"})

    def _remember_user(self, user_name: str, fact: str) -> str:
        if not self.memory_store:
            return json.dumps({"error": "Memory is not enabled."})
        if not user_name or not fact:
            return json.dumps({"error": "Both user_name and fact are required."})

        # Reverse-lookup user_id from display name
        user_id = None
        for uid, name in self.participants.items():
            if name.lower() == user_name.lower():
                user_id = uid
                break

        if user_id is None:
            return json.dumps({"error": f"Could not find user '{user_name}' in this conversation."})

        self.memory_store.add_user_memory(user_id, user_name, fact)
        return json.dumps({"status": "ok", "message": f"Remembered about {user_name}: {fact}"})

    def _remember_channel(self, memory: str) -> str:
        if not self.memory_store:
            return json.dumps({"error": "Memory is not enabled."})
        if not memory:
            return json.dumps({"error": "Memory text is required."})

        self.memory_store.add_channel_memory(self.channel_id, memory)
        return json.dumps({"status": "ok", "message": f"Remembered for this channel: {memory}"})
