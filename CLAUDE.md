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

All LLM providers share two config fields: `api_key` and `model` under `[backend]`. Provider-specific options (`base_url` for openai-compatible, `host` for Ollama) are optional. `base_url` is required for the openai-compatible backend.

## Architecture

Faithful is a Discord bot that emulates a persona by learning from example messages. It uses discord.py's cog system and a pluggable backend architecture.

### Request Flow

1. **`cogs/chat.py`** receives a Discord message, decides whether to respond (mention, reply, active conversation, or random chance), and starts a debounced task. If not replying, `_maybe_react()` may trigger a standalone reaction.
2. **`prompt.py`** assembles a `GenerationRequest` -- slices history from the last @mention, samples examples from the store, injects custom emoji list via `get_guild_emojis()`, and formats the system prompt.
3. The active **backend** generates a response from the `GenerationRequest`.
4. **`chunker.py`** calls `extract_reactions()` to strip `[react: emoji]` markers, splits the clean text into Discord-safe chunks (<=2000 chars), sends them with simulated typing delays, and applies extracted reactions to the prompt message.

### Backend System

All backends extend the single `Backend` ABC in `backends/base.py`. There is no separate `BaseLLMBackend` -- the base class itself provides the tool loop, `generate()`, and helper methods. Subclasses implement `_call_api(system_prompt, messages)` for basic generation, and optionally three tool hooks for tool-use support:
- `_format_tools(tools)` -- convert provider-agnostic defs to provider format
- `_call_with_tools(system_prompt, messages, tools, attachments)` -- call API with tools, return `(text, list[ToolCall])`
- `_append_tool_result(messages, call, result)` -- append tool result in provider format

The tool loop lives in `Backend._generate_with_tools()` (max 5 rounds). It's only invoked when `_get_active_tools()` returns tools (memory tools, or DuckDuckGo web search for backends without native search).

Backend files are named without a `_backend` suffix: `openai.py`, `openai_compat.py`, `ollama.py`, `gemini.py`, `anthropic.py`. They are registered in `backends/__init__.py` and instantiated via `get_backend(name, config)`.

**Shared helpers** in the `Backend` base class:
- `Attachment.b64` property -- base64-encodes attachment data (used by all backends that handle images)
- `Backend._parse_json_args(raw)` -- safely parses JSON tool argument strings with fallback to empty dict

Each LLM API handles system prompts differently:
- **OpenAI**: `"developer"` role in input messages (Responses API)
- **OpenAI-compatible**: `"system"` role prepended to messages (Chat Completions API)
- **Ollama**: `"system"` role prepended to messages
- **Gemini**: `system_instruction` in `GenerateContentConfig`
- **Anthropic**: `system=` parameter (separate from messages), plus `_normalize_messages()` to enforce role alternation

### Tool System

**Web search** uses native server-side tools for OpenAI (`web_search_preview`), Anthropic (`web_search_20250305`), and Gemini (`GoogleSearch` grounding). These are handled by each API automatically -- no tool loop needed. Ollama and openai-compatible fall back to DuckDuckGo via `duckduckgo_search` through the client-side tool loop. Backends with native search set `_has_native_search = True` so `_get_active_tools()` skips the DuckDuckGo tool.

Provider-agnostic tool definitions for memory tools live in `tools.py`: `remember_user` (reverse-lookups user ID from display name), `remember_channel`. `ToolExecutor` dispatches calls and returns JSON results.

### Reactions

Responses can include `[react: emoji]` markers at the end. The flow:

1. The **system prompt** instructs the persona to use `[react: emoji]` markers and lists available custom emoji via the `{custom_emojis}` placeholder.
2. `get_guild_emojis()` in `prompt.py` builds the custom emoji list from the guild's available emojis.
3. `extract_reactions()` in `chunker.py` strips markers from the response text and returns them separately.
4. `send_chunked()` applies the reactions to the prompt message after sending text chunks.
5. `_maybe_react()` in `cogs/chat.py` independently triggers reactions on messages the bot doesn't reply to, controlled by `reaction_probability`.

### Memory System

`memory.py` provides `MemoryStore` -- JSON file storage in `data/memories/users/{user_id}.json` and `data/memories/channels/{channel_id}.json`. Caps: 20 facts/user, 50 memories/channel (FIFO). Memories are injected into the system prompt via `format_memories()` in `prompt.py`. Admin commands in `/memory` group manage memories manually.

### Admin Commands

All admin commands use a single permission tier -- any user whose ID is in `admin_ids` can run them. The `is_admin()` check decorator enforces this. Available commands:

- `/upload`, `/add_message`, `/list_messages`, `/remove_message`, `/clear_messages`, `/download_messages` -- manage the example corpus
- `/status` -- show current configuration
- `/generate_test` -- test generation with a prompt
- `/memory list|add|remove|clear` -- manage memories
- "Add to Persona" context menu -- right-click a message to add it as an example

### Key Design Decisions

- **`GenerationRequest`** is a frozen dataclass containing the formatted system prompt, user prompt, conversation context, `channel_id`, `guild_id`, and `participants` dict
- **`format_system_prompt()`** in `prompt.py` handles template formatting with persona name, examples, memories, and custom emoji via `{custom_emojis}` placeholder
- **`store.get_sampled_messages()`** uses index-based tracking to avoid duplicates when balancing samples across source files
- **Scheduler** uses a plain `asyncio.Task` loop with persistent state in `scheduler_state.json`
- **Debouncing** in chat uses per-channel `asyncio.Task` cancellation
- **`remember_user`** tool uses display name (not user_id) since the LLM sees names in context, not IDs
- Both `enable_web_search` and `enable_memory` default to `false` -- zero behavior change without opt-in
- Config is read-only at runtime -- no `save()` or `set_*` commands; edit `config.toml` and restart
