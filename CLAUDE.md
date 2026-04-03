# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
pip install .                          # install dependencies
cp config.example.toml config.toml     # configure (token + admin_ids required)
python -m faithful                     # run
```

For development: `pip install -e .`

There is no test suite, linter, or CI pipeline configured.

## Configuration

Config lives in `config.toml` (TOML format). Configuration is **read-only** -- there is no runtime persistence or `save()` method; all changes require editing the file and restarting.

Environment variables override their TOML equivalents for deployment flexibility:
- `DISCORD_TOKEN` -- overrides `discord.token`
- `ADMIN_USER_IDS` (comma-separated) or `ADMIN_USER_ID` -- overrides `discord.admin_ids`
- `API_KEY` -- overrides `backend.api_key`

`admin_ids` accepts a list of Discord user IDs (multi-admin support). The legacy singular `admin_user_id` key is still read as a fallback.

Notable config fields:
- `reaction_probability` (default 0.05) -- chance the bot reacts to a message it doesn't reply to
- `enable_web_search` and `enable_memory` default to `false` -- zero behavior change without opt-in
- `enable_thinking` (default true), `enable_compaction` (default true), `enable_1m_context` (default true) -- Anthropic-specific features; ignored by other backends
- `max_session_messages` (default 50) -- per-channel session history window (all backends)

All LLM providers share two config fields: `api_key` and `model` under `[backend]`. Provider-specific options (`base_url` for openai-compatible) are optional. `base_url` is required for the openai-compatible backend. Local models via Ollama use the openai-compatible backend with `base_url = "http://localhost:11434/v1"`.

## Architecture

Faithful is a Discord bot that emulates a persona by learning from example messages. It uses discord.py's cog system and a pluggable backend architecture.

### Request Flow

1. **`cogs/chat.py`** receives a Discord message, decides whether to respond (mention, reply, active conversation, or random chance), and starts a debounced task. If not replying, `_maybe_react()` may trigger a standalone reaction.
2. **`prompt.py`** assembles a `GenerationRequest` -- slices history from the last @mention, samples examples from the store, injects custom emoji list via `get_guild_emojis()`, and formats the system prompt.
3. The active **backend** generates a response from the `GenerationRequest`, using **session history** (per-channel, sliding window with expiry) to maintain context across turns, including tool-call/tool-result pairs.
4. **`chunker.py`** calls `extract_reactions()` to strip `[react: emoji]` markers, splits clean text into Discord-safe chunks (<=2000 chars) via `_chunk_text()`, sends them via `send_responses()` (first chunk replies to the original message, rest are standalone), and applies extracted reactions to the prompt message.

### Backend System

All backends extend the single `Backend` ABC in `backends/base.py`. There is no separate `BaseLLMBackend` -- the base class itself provides the tool loop, `generate()`, session history management, and helper methods. Subclasses implement `_call_api(system_prompt, messages)` for basic generation, and optionally three tool hooks for tool-use support:
- `_format_tools(tools)` -- convert provider-agnostic defs to provider format
- `_call_with_tools(system_prompt, messages, tools, attachments)` -- call API with tools, return `(text, list[ToolCall])`
- `_append_tool_result(messages, call, result)` -- append tool result in provider format

The tool loop lives in `Backend._generate_with_tools()` (max 5 rounds). It's only invoked when `_get_active_tools()` returns tools (memory tools, or DuckDuckGo web search for backends without native search).

**Session history:** `Backend` maintains a `_sessions: dict[int, SessionHistory]` keyed by channel ID. `SessionHistory` stores messages in a provider-agnostic format (including tool-call/tool-result pairs). On cold start, sessions are seeded from Discord-fetched history; on subsequent turns, the session is the source of truth. Sessions expire after `conversation_expiry` seconds of inactivity and are trimmed to `max_session_messages`. Tool interactions are stored via `_store_tool_round()` in a synthetic format (`tool_calls` key, `tool_results` role) that all backends filter out when building API-specific messages.

Backend files are named without a `_backend` suffix: `openai.py`, `openai_compat.py`, `gemini.py`, `anthropic.py`. They are registered in `backends/__init__.py` and instantiated via `get_backend(name, config)`. Local models (Ollama, LM Studio, vLLM, etc.) use the openai-compatible backend.

**Shared helpers** in the `Backend` base class:
- `Attachment.b64` property -- base64-encodes attachment data (used by all backends that handle images)
- `Backend._parse_json_args(raw)` -- safely parses JSON tool argument strings with fallback to empty dict

Each LLM API handles system prompts differently:
- **OpenAI**: `"developer"` role in input messages (Responses API)
- **OpenAI-compatible**: `"system"` role prepended to messages (Chat Completions API)

- **Gemini**: `system_instruction` in `GenerateContentConfig`
- **Anthropic**: `system=` parameter (separate from messages) with `cache_control: ephemeral` for prompt caching, plus `_normalize_messages()` to enforce role alternation. Uses streaming (`beta.messages.stream`), adaptive thinking, context compaction, and beta headers (1M context). All controlled by config flags.

### Tool System

**Server-side tools (Anthropic):** The Anthropic backend uses native server-side tools: `web_search_20260209`, `web_fetch_20260209`, and `code_execution_20260120`. These run on Anthropic's infrastructure and support `pause_turn` continuation (capped at 10 rounds). The `_native_server_tools()` method returns them when `enable_web_search` is true.

**Server-side tools (OpenAI, Gemini):** OpenAI uses `web_search_preview` and Gemini uses `GoogleSearch` grounding for native web search. Both set `_has_native_server_tools = True` so `_get_active_tools()` skips client-side web tools.

**Client-side web tools:** The openai-compatible backend falls back to DuckDuckGo search and `aiohttp`-based web fetch (`TOOL_WEB_SEARCH`, `TOOL_WEB_FETCH` in `tools.py`) through the client-side tool loop.

**Memory tool:** Uses Anthropic's file-based CRUD model (`memory_20250818`) across all backends. Claude manages plain files in `data/memories/` with commands: `view`, `create`, `str_replace`, `insert`, `delete`, `rename`. The `MemoryExecutor` class in `tools.py` handles execution with path traversal protection. Anthropic gets the native tool type; other backends get `TOOL_MEMORY` as a client-side tool (controlled by `_has_native_memory` flag). For non-Anthropic backends, a memory protocol instruction is injected into the system prompt.

Provider-agnostic tool definitions live in `tools.py`. `ToolExecutor` dispatches calls to `MemoryExecutor`, DuckDuckGo search, or aiohttp web fetch.

### Reactions

Responses can include `[react: emoji]` markers at the end. The flow:

1. The **system prompt** instructs the persona to use `[react: emoji]` markers and lists available custom emoji via the `{custom_emojis}` placeholder.
2. `get_guild_emojis()` in `prompt.py` builds the custom emoji list from the guild's available emojis.
3. `extract_reactions()` in `chunker.py` strips markers from the response text and returns them separately.
4. `send_responses()` reply-threads the first chunk to the original message, sends the rest standalone, and applies reactions to the prompt message.
5. `_maybe_react()` in `cogs/chat.py` independently triggers reactions on messages the bot doesn't reply to, controlled by `reaction_probability`.

### Memory System

Plain file storage in `data/memories/`. Claude organizes files however it wants -- no imposed structure. `MemoryExecutor` in `tools.py` executes file CRUD commands matching Anthropic's documented memory tool interface. Path traversal is blocked via `pathlib.Path.resolve()` + `relative_to()`. The directory is created on startup when `enable_memory` is true (`bot.py` sets `backend.memory_base_dir`).

### Admin Commands

All admin commands use a single permission tier -- any user whose ID is in `admin_ids` can run them. The `is_admin()` check decorator enforces this. Available commands:

- `/upload`, `/add_message`, `/list_messages`, `/remove_message`, `/clear_messages`, `/download_messages` -- manage the example corpus
- `/status` -- show current configuration
- `/generate_test` -- test generation with a prompt
- "Add to Persona" context menu -- right-click a message to add it as an example

### Key Design Decisions

- **`GenerationRequest`** is a frozen dataclass containing the formatted system prompt, user prompt, conversation context, `channel_id`, `guild_id`, and `participants` dict
- **`format_system_prompt()`** in `prompt.py` handles template formatting with persona name, examples, custom emoji, and optional memory protocol injection for non-Anthropic backends
- **`store.get_sampled_messages()`** uses index-based tracking to avoid duplicates when balancing samples across source files
- **Scheduler** uses a plain `asyncio.Task` loop with persistent state in `scheduler_state.json`
- **Debouncing** in chat uses per-channel `asyncio.Task` cancellation
- **`enable_web_search`** controls all server-side tools (search, fetch, code execution) for Anthropic and client-side web tools (DuckDuckGo, aiohttp fetch) for other backends
- Both `enable_web_search` and `enable_memory` default to `false` -- zero behavior change without opt-in
- Config is read-only at runtime -- no `save()` or `set_*` commands; edit `config.toml` and restart
