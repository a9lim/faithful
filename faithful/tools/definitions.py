"""Provider-agnostic tool definitions."""

from __future__ import annotations

from typing import Any

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
