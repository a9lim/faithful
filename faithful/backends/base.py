from __future__ import annotations

import base64
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from faithful.config import Config
    from faithful.memory import MemoryStore

log = logging.getLogger("faithful.llm")

SPONTANEOUS_PROMPT = (
    "Say something in the chat. Be random -- start a topic, share a thought, "
    "drop a reaction to nothing. Whatever feels in-character."
)

MAX_TOOL_ROUNDS = 5


@dataclass(frozen=True)
class Attachment:
    """A downloaded file attachment (image, etc.) from a Discord message."""

    filename: str
    content_type: str
    data: bytes

    @property
    def b64(self) -> str:
        return base64.b64encode(self.data).decode()


@dataclass
class ToolCall:
    """A tool invocation parsed from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationRequest:
    """Everything a backend needs to produce a response."""

    prompt: str
    system_prompt: str
    context: list[dict[str, str]] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    channel_id: int = 0
    guild_id: int = 0
    participants: dict[int, str] = field(default_factory=dict)


class Backend(ABC):
    """Base class for all text-generation backends.

    Subclasses implement ``_call_api`` for basic generation.
    For tool support, subclasses also implement ``_format_tools``,
    ``_call_with_tools``, and ``_append_tool_result``.
    """

    memory_store: MemoryStore | None = None

    _has_native_search: bool = False
    """Subclasses with server-side web search set this to True."""

    def __init__(self, config: Config) -> None:
        self.config = config

    async def setup(self, examples: list[str]) -> None:
        """Called when the example corpus changes (or on first load)."""

    @abstractmethod
    async def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        attachments: list[Attachment] | None = None,
    ) -> str:
        """Send messages to the provider and return the response text."""

    @staticmethod
    def _parse_json_args(raw: str | None) -> dict[str, Any]:
        """Parse a JSON argument string with fallback to empty dict."""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_active_tools(self) -> list[dict[str, Any]]:
        """Return provider-agnostic tool defs enabled by config."""
        from faithful.tools import TOOL_REMEMBER_CHANNEL, TOOL_REMEMBER_USER, TOOL_WEB_SEARCH

        tools: list[dict[str, Any]] = []
        if self.config.enable_web_search and not self._has_native_search:
            tools.append(TOOL_WEB_SEARCH)
        if self.config.enable_memory and self.memory_store is not None:
            tools.append(TOOL_REMEMBER_USER)
            tools.append(TOOL_REMEMBER_CHANNEL)
        return tools

    async def generate(self, request: GenerationRequest) -> str:
        messages: list[dict[str, str]] = list(request.context)

        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        elif request.attachments:
            messages.append({"role": "user", "content": ""})
        else:
            messages.append({"role": "user", "content": SPONTANEOUS_PROMPT})

        tools = self._get_active_tools()
        if tools:
            return await self._generate_with_tools(
                request.system_prompt,
                messages,
                tools,
                request.attachments or None,
                request.channel_id,
                request.participants,
            )

        return await self._call_api(
            request.system_prompt, messages, request.attachments or None
        )

    async def _generate_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: list[dict[str, Any]],
        attachments: list[Attachment] | None,
        channel_id: int,
        participants: dict[int, str],
    ) -> str:
        from faithful.tools import ToolExecutor

        formatted_tools = self._format_tools(tools)
        executor = ToolExecutor(self.memory_store, channel_id, participants)

        for _ in range(MAX_TOOL_ROUNDS):
            text, tool_calls = await self._call_with_tools(
                system_prompt, messages, formatted_tools, attachments
            )
            # Only pass attachments on the first round
            attachments = None

            if not tool_calls:
                return (text or "").strip()

            for call in tool_calls:
                result = await executor.execute(call.name, call.arguments)
                log.info("Tool %s(%s) -> %s", call.name, call.arguments, result[:200])
                messages = self._append_tool_result(messages, call, result)

        # Exhausted rounds -- do a final call without tools
        return await self._call_api(system_prompt, messages)

    def _format_tools(self, tools: list[dict[str, Any]]) -> Any:
        """Convert provider-agnostic tool defs to provider format."""
        raise NotImplementedError

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[Any],
        tools: Any,
        attachments: list[Attachment] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Call the API with tools. Return (text_response, tool_calls)."""
        raise NotImplementedError

    def _append_tool_result(
        self,
        messages: list[Any],
        call: ToolCall,
        result: str,
    ) -> list[Any]:
        """Append a tool call and its result to messages in provider format."""
        raise NotImplementedError
