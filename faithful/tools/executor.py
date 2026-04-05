"""Tool call dispatcher — routes calls to the appropriate executor."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from faithful.tools.memory import MemoryExecutor

log = logging.getLogger("faithful.tools")


class ToolExecutor:
    """Executes tool calls, dispatching to the appropriate implementation."""

    def __init__(
        self,
        memory_base_dir: Path | None,
        channel_id: int,
        participants: dict[int, str],
    ) -> None:
        self.channel_id = channel_id
        self.participants = participants
        self._memory = MemoryExecutor(memory_base_dir) if memory_base_dir else None

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool by name and return the result as a string."""
        try:
            if name == "web_search":
                return await self._web_search(args.get("query", ""))
            elif name == "web_fetch":
                return await self._web_fetch(args.get("url", ""))
            elif name == "memory":
                return self._memory_dispatch(args)
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

    async def _web_fetch(self, url: str) -> str:
        if not url:
            return json.dumps({"error": "Empty URL."})

        try:
            import aiohttp
        except ImportError:
            return json.dumps({"error": "Web fetch unavailable (aiohttp not installed)."})
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return json.dumps({"error": "Web fetch unavailable (beautifulsoup4 not installed)."})

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return json.dumps({"error": f"HTTP {resp.status} for {url}"})
                    content_type = resp.content_type or ""
                    if "html" in content_type or "text" in content_type:
                        raw = await resp.text(errors="replace")
                        if "html" in content_type:
                            soup = BeautifulSoup(raw, "html.parser")
                            text = soup.get_text(separator="\n", strip=True)
                        else:
                            text = raw
                        # Truncate to ~50k chars
                        if len(text) > 50_000:
                            text = text[:50_000] + "\n\n[Content truncated]"
                        return json.dumps({"url": url, "content": text})
                    else:
                        return json.dumps({"error": f"Unsupported content type: {content_type}"})
        except Exception as e:
            return json.dumps({"error": f"Fetch failed: {e}"})

    def _memory_dispatch(self, args: dict[str, Any]) -> str:
        if self._memory is None:
            return "Error: Memory is not enabled."
        return self._memory.execute(args)
