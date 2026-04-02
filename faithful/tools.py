"""Provider-agnostic tool definitions and executor."""

from __future__ import annotations

import json
import logging
import shutil
import urllib.parse
from pathlib import Path
from typing import Any

from faithful.backends.base import ToolCall as ToolCall  # noqa: F401

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

TOOL_WEB_FETCH: dict[str, Any] = {
    "name": "web_fetch",
    "description": "Fetch the full text content of a web page at the given URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch.",
            },
        },
        "required": ["url"],
    },
}

TOOL_MEMORY: dict[str, Any] = {
    "name": "memory",
    "description": "Manage persistent memory files. Use to store and retrieve information across conversations.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["view", "create", "str_replace", "insert", "delete", "rename"],
                "description": "The memory operation to perform.",
            },
            "path": {
                "type": "string",
                "description": "File or directory path (e.g. /memories or /memories/notes.txt).",
            },
            "file_text": {
                "type": "string",
                "description": "Content for the 'create' command.",
            },
            "old_str": {
                "type": "string",
                "description": "Text to find for 'str_replace'.",
            },
            "new_str": {
                "type": "string",
                "description": "Replacement text for 'str_replace'.",
            },
            "insert_line": {
                "type": "integer",
                "description": "Line number for 'insert' (0-indexed insertion point).",
            },
            "insert_text": {
                "type": "string",
                "description": "Text to insert for 'insert'.",
            },
            "view_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional [start, end] line range for 'view'.",
            },
            "old_path": {
                "type": "string",
                "description": "Source path for 'rename'.",
            },
            "new_path": {
                "type": "string",
                "description": "Destination path for 'rename'.",
            },
        },
        "required": ["command"],
    },
}

TOOL_CONTINUE: dict[str, Any] = {
    "name": "continue",
    "description": (
        "Signal that you want to send another follow-up message. Call this when "
        "you have more to say — your current text will be sent immediately, then "
        "you get another turn to speak. Do NOT use this if you're done talking."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


# ── Memory executor ──────────────────────────────────────

class MemoryExecutor:
    """Executes memory tool commands against a local file directory.

    All paths from the LLM use ``/memories`` as root. This class maps them
    to ``base_dir`` and validates they stay within it.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir.resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, virtual_path: str) -> Path:
        """Map a ``/memories/...`` virtual path to a real path under base_dir."""
        decoded = urllib.parse.unquote(virtual_path)
        if ".." in decoded:
            raise ValueError(f"Path traversal detected: {virtual_path}")
        # Strip leading /memories or /memories/
        stripped = decoded
        if stripped.startswith("/memories"):
            stripped = stripped[len("/memories"):]
        stripped = stripped.lstrip("/")
        resolved = (self._base / stripped).resolve()
        # Ensure it's still within base
        try:
            resolved.relative_to(self._base)
        except ValueError:
            raise ValueError(f"Path escapes memory directory: {virtual_path}")
        return resolved

    def execute(self, args: dict[str, Any]) -> str:
        """Dispatch a memory command and return the result string."""
        command = args.get("command", "")
        try:
            if command == "view":
                return self._view(args)
            elif command == "create":
                return self._create(args)
            elif command == "str_replace":
                return self._str_replace(args)
            elif command == "insert":
                return self._insert(args)
            elif command == "delete":
                return self._delete(args)
            elif command == "rename":
                return self._rename(args)
            else:
                return f"Error: Unknown command '{command}'"
        except ValueError as e:
            return str(e)
        except Exception as e:
            log.exception("Memory command '%s' failed.", command)
            return f"Error: {e}"

    def _view(self, args: dict[str, Any]) -> str:
        path_str = args.get("path", "/memories")
        resolved = self._resolve(path_str)

        if not resolved.exists():
            return f"The path {path_str} does not exist. Please provide a valid path."

        if resolved.is_dir():
            return self._list_dir(path_str, resolved)

        # File
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > 999_999:
            return f"File {path_str} exceeds maximum line limit of 999,999 lines."

        view_range = args.get("view_range")
        if view_range and len(view_range) == 2:
            start, end = int(view_range[0]), int(view_range[1])
            # 1-indexed
            selected = lines[start - 1 : end]
            start_num = start
        else:
            selected = lines
            start_num = 1

        numbered = []
        for i, line in enumerate(selected, start=start_num):
            numbered.append(f"{i:6d}\t{line}")

        return f"Here's the content of {path_str} with line numbers:\n" + "\n".join(numbered)

    def _list_dir(self, path_str: str, resolved: Path) -> str:
        entries: list[tuple[str, int]] = []
        base_depth = len(resolved.parts)
        for item in sorted(resolved.rglob("*")):
            if any(p.startswith(".") for p in item.relative_to(resolved).parts):
                continue
            depth = len(item.parts) - base_depth
            if depth > 2:
                continue
            size = item.stat().st_size if item.is_file() else sum(
                f.stat().st_size for f in item.rglob("*") if f.is_file()
            )
            entries.append((str(item.relative_to(resolved.parent)), size))

        # Format sizes
        def fmt_size(s: int) -> str:
            if s >= 1_048_576:
                return f"{s / 1_048_576:.1f}M"
            elif s >= 1024:
                return f"{s / 1024:.1f}K"
            else:
                return f"{s}B" if s > 0 else "0B"

        # Include the root dir itself
        total = sum(
            f.stat().st_size for f in resolved.rglob("*") if f.is_file()
        )
        lines = [f"{fmt_size(total)}\t{path_str}"]
        for name, size in entries:
            lines.append(f"{fmt_size(size)}\t/{name}")

        header = (
            f"Here're the files and directories up to 2 levels deep in {path_str}, "
            "excluding hidden items and node_modules:\n"
        )
        return header + "\n".join(lines)

    def _create(self, args: dict[str, Any]) -> str:
        path_str = args.get("path", "")
        resolved = self._resolve(path_str)
        if resolved.exists():
            return f"Error: File {path_str} already exists"
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(args.get("file_text", ""), encoding="utf-8")
        return f"File created successfully at: {path_str}"

    def _str_replace(self, args: dict[str, Any]) -> str:
        path_str = args.get("path", "")
        resolved = self._resolve(path_str)
        if not resolved.exists() or resolved.is_dir():
            return f"Error: The path {path_str} does not exist. Please provide a valid path."

        old_str = args.get("old_str", "")
        new_str = args.get("new_str", "")
        content = resolved.read_text(encoding="utf-8", errors="replace")

        # Check occurrences
        count = content.count(old_str)
        if count == 0:
            return f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path_str}."
        if count > 1:
            lines = content.splitlines()
            line_nums = [
                i + 1 for i, line in enumerate(lines) if old_str in line
            ]
            return (
                f"No replacement was performed. Multiple occurrences of old_str "
                f"`{old_str}` in lines: {line_nums}. Please ensure it is unique"
            )

        new_content = content.replace(old_str, new_str, 1)
        resolved.write_text(new_content, encoding="utf-8")

        # Show snippet around the replacement
        new_lines = new_content.splitlines()
        # Find where the replacement landed
        for i, line in enumerate(new_lines):
            if new_str in line:
                start = max(0, i - 2)
                end = min(len(new_lines), i + 3)
                snippet = "\n".join(
                    f"{j + 1:6d}\t{new_lines[j]}" for j in range(start, end)
                )
                return f"The memory file has been edited.\n{snippet}"

        return "The memory file has been edited."

    def _insert(self, args: dict[str, Any]) -> str:
        path_str = args.get("path", "")
        resolved = self._resolve(path_str)
        if not resolved.exists() or resolved.is_dir():
            return f"Error: The path {path_str} does not exist"

        insert_line = args.get("insert_line", 0)
        insert_text = args.get("insert_text", "")

        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        n_lines = len(lines)
        if insert_line < 0 or insert_line > n_lines:
            return (
                f"Error: Invalid `insert_line` parameter: {insert_line}. "
                f"It should be within the range of lines of the file: [0, {n_lines}]"
            )

        new_lines = insert_text.splitlines()
        lines[insert_line:insert_line] = new_lines
        resolved.write_text("\n".join(lines), encoding="utf-8")
        return f"The file {path_str} has been edited."

    def _delete(self, args: dict[str, Any]) -> str:
        path_str = args.get("path", "")
        resolved = self._resolve(path_str)
        if not resolved.exists():
            return f"Error: The path {path_str} does not exist"
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()
        return f"Successfully deleted {path_str}"

    def _rename(self, args: dict[str, Any]) -> str:
        old_path_str = args.get("old_path", "")
        new_path_str = args.get("new_path", "")
        old_resolved = self._resolve(old_path_str)
        new_resolved = self._resolve(new_path_str)

        if not old_resolved.exists():
            return f"Error: The path {old_path_str} does not exist"
        if new_resolved.exists():
            return f"Error: The destination {new_path_str} already exists"

        new_resolved.parent.mkdir(parents=True, exist_ok=True)
        old_resolved.rename(new_resolved)
        return f"Successfully renamed {old_path_str} to {new_path_str}"


# ── Tool executor ────────────────────────────────────────

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

        import aiohttp
        from bs4 import BeautifulSoup

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
