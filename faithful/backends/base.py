from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from faithful.config import Config

log = logging.getLogger("faithful.llm")

SPONTANEOUS_PROMPT = (
    "Say something in the chat. Be random -- start a topic, share a thought, "
    "drop a reaction to nothing. Whatever feels in-character."
)

MAX_TOOL_ROUNDS = 5
MAX_CONTINUES = 5


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


class SessionHistory:
    """Per-channel conversation state with sliding window and expiry."""

    __slots__ = ("channel_id", "messages", "last_activity", "max_messages", "_expiry")

    def __init__(self, channel_id: int, max_messages: int, expiry: float) -> None:
        self.channel_id = channel_id
        self.messages: list[dict[str, Any]] = []
        self.last_activity: float = time.monotonic()
        self.max_messages = max_messages
        self._expiry = expiry

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.last_activity) > self._expiry

    def touch(self) -> None:
        """Update last-activity timestamp."""
        self.last_activity = time.monotonic()

    def append(self, message: dict[str, Any]) -> None:
        """Add a message to the session."""
        self.messages.append(message)

    def seed(self, context: list[dict[str, str]]) -> None:
        """Seed session from Discord-fetched history (cold start)."""
        self.messages = [dict(m) for m in context]

    def trim(self) -> None:
        """Trim to max_messages, removing from the front."""
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]


class Backend(ABC):
    """Base class for all text-generation backends.

    Subclasses implement ``_call_api`` for basic generation.
    For tool support, subclasses also implement ``_format_tools``,
    ``_call_with_tools``, and ``_append_tool_result``.
    """

    memory_base_dir: Path | None = None
    """Set by the bot to data_dir / "memories" when memory is enabled."""

    _has_native_server_tools: bool = False
    """Subclasses with server-side web search/fetch/code-execution set this to True."""

    _has_native_memory: bool = False
    """Subclasses with a native memory tool type set this to True."""

    _sessions: dict[int, SessionHistory]

    def __init__(self, config: Config) -> None:
        self.config = config
        self._sessions = {}

    def _get_session(self, channel_id: int) -> SessionHistory:
        """Return existing session or create a new one. Expired sessions are reset."""
        session = self._sessions.get(channel_id)
        if session is None or session.expired:
            session = SessionHistory(
                channel_id=channel_id,
                max_messages=self.config.max_session_messages,
                expiry=self.config.conversation_expiry,
            )
            self._sessions[channel_id] = session
        return session

    def _store_tool_round(
        self,
        session: SessionHistory,
        call: ToolCall,
        result: str,
    ) -> None:
        """Append a tool call + result to the session in provider-agnostic format."""
        session.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": call.id, "name": call.name, "arguments": call.arguments}],
        })
        session.append({
            "role": "tool_results",
            "results": [{"tool_call_id": call.id, "content": result}],
        })

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
        from faithful.tools import (
            TOOL_CONTINUE,
            TOOL_MEMORY,
            TOOL_WEB_FETCH,
            TOOL_WEB_SEARCH,
        )

        tools: list[dict[str, Any]] = []
        if self.config.enable_web_search and not self._has_native_server_tools:
            tools.append(TOOL_WEB_SEARCH)
            tools.append(TOOL_WEB_FETCH)
        # Anthropic backend adds memory as a native tool type in _format_tools;
        # other backends need the generic TOOL_MEMORY definition here.
        if self.config.enable_memory and not self._has_native_memory:
            tools.append(TOOL_MEMORY)
        tools.append(TOOL_CONTINUE)
        return tools

    async def generate(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Generate response text, yielding each message as it's ready."""
        session = self._get_session(request.channel_id)
        session.touch()

        # Seed from Discord history on cold start; otherwise ignore request.context
        if not session.messages:
            session.seed(request.context)

        # Append current user message
        if request.prompt:
            session.append({"role": "user", "content": request.prompt})
        elif request.attachments:
            session.append({"role": "user", "content": ""})
        else:
            session.append({"role": "user", "content": SPONTANEOUS_PROMPT})

        tools = self._get_active_tools()
        collected_text: list[str] = []

        async for text in self._generate_with_tools(
            request.system_prompt,
            session,
            tools,
            request.attachments or None,
            request.channel_id,
            request.participants,
        ):
            collected_text.append(text)
            yield text

        # Store final assistant response in session
        if collected_text:
            session.append({"role": "assistant", "content": "\n\n".join(collected_text)})

        session.trim()

    async def _generate_with_tools(
        self,
        system_prompt: str,
        session: SessionHistory,
        tools: list[dict[str, Any]],
        attachments: list[Attachment] | None,
        channel_id: int,
        participants: dict[int, str],
    ) -> AsyncGenerator[str, None]:
        from faithful.tools import ToolExecutor

        formatted_tools = self._format_tools(tools)
        executor = ToolExecutor(self.memory_base_dir, channel_id, participants)
        continue_count = 0

        # Build a working copy of messages for the API call.
        # Provider-specific tool results get appended here during the loop.
        messages: list[Any] = list(session.messages)

        for _ in range(MAX_TOOL_ROUNDS + MAX_CONTINUES):
            text, tool_calls = await self._call_with_tools(
                system_prompt, messages, formatted_tools, attachments
            )
            # Only pass attachments on the first round
            attachments = None

            if not tool_calls:
                if text:
                    yield text.strip()
                return

            # Separate continue from regular tool calls
            wants_continue = False
            for call in tool_calls:
                if call.name == "continue":
                    wants_continue = True
                    messages = self._append_tool_result(
                        messages, call, '{"status": "ok"}'
                    )
                else:
                    result = await executor.execute(call.name, call.arguments)
                    log.info(
                        "Tool %s(%s) -> %s",
                        call.name, call.arguments, result[:200],
                    )
                    messages = self._append_tool_result(messages, call, result)
                    # Persist tool round in session (provider-agnostic)
                    self._store_tool_round(session, call, result)

            if wants_continue and continue_count < MAX_CONTINUES:
                if text:
                    yield text.strip()
                continue_count += 1
            # Otherwise loop continues to get the LLM's response to tool results

        # Exhausted rounds — do a final call without tools
        final = await self._call_api(system_prompt, messages)
        if final:
            yield final.strip()

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
