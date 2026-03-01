# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
pip install .                          # install dependencies
cp config.example.toml config.toml     # configure (token + admin_user_id required)
python -m faithful                     # run
```

For development: `pip install -e .`

There is no test suite, linter, or CI pipeline configured.

## Configuration

Config lives in `config.toml` (TOML format). Environment variables `DISCORD_TOKEN`, `ADMIN_USER_ID`, and `API_KEY` override their TOML equivalents for deployment flexibility.

All LLM providers share two config fields: `api_key` and `model` under `[backend]`. Provider-specific options (`base_url` for OpenAI-compatible APIs, `host` for Ollama) are optional.

## Architecture

Faithful is a Discord bot that emulates a persona by learning from example messages. It uses discord.py's cog system and a pluggable backend architecture.

### Request Flow

1. **`cogs/chat.py`** receives a Discord message, decides whether to respond (mention, reply, active conversation, or random chance), and starts a debounced task
2. **`prompt.py`** assembles a `GenerationRequest` — slices history from the last @mention, samples examples from the store, and formats the system prompt
3. The active **backend** generates a response from the `GenerationRequest`
4. **`chunker.py`** splits the response into Discord-safe chunks (<=2000 chars) and sends them with simulated typing delays

### Backend System

All backends implement `Backend` (in `backends/base.py`) with `setup(examples)` and `generate(request)`. LLM backends extend `BaseLLMBackend` (`backends/llm.py`) — subclasses implement `_call_api(system_prompt, messages)` for basic generation, and optionally three tool hooks for tool-use support:
- `_format_tools(tools)` — convert provider-agnostic defs to provider format
- `_call_with_tools(system_prompt, messages, tools, attachments)` — call API with tools, return `(text, list[ToolCall])`
- `_append_tool_result(messages, call, result)` — append tool result in provider format

The tool loop lives in `BaseLLMBackend._generate_with_tools()` (max 5 rounds). It's only invoked when `_get_active_tools()` returns tools (based on `enable_web_search` / `enable_memory` config flags). Backends without tool support (Markov) are unaffected.

Each LLM API handles system prompts differently:
- **OpenAI**: `"developer"` role in input messages (Responses API)
- **Ollama**: `"system"` role prepended to messages
- **Gemini**: `system_instruction` in `GenerateContentConfig`
- **Anthropic**: `system=` parameter (separate from messages), plus `_normalize_messages()` to enforce role alternation

Backends are registered in `backends/__init__.py` and instantiated via `get_backend(name, config)`.

### Tool System

Provider-agnostic tool definitions live in `tools.py`. Three tools: `web_search` (DuckDuckGo via `duckduckgo_search`), `remember_user` (reverse-lookups user ID from display name), `remember_channel`. `ToolExecutor` dispatches calls and returns JSON results.

### Memory System

`memory.py` provides `MemoryStore` — JSON file storage in `data/memories/users/{user_id}.json` and `data/memories/channels/{channel_id}.json`. Caps: 20 facts/user, 50 memories/channel (FIFO). Memories are injected into the system prompt via `format_memories()` in `prompt.py`. Admin commands in `/memory` group manage memories manually.

### Key Design Decisions

- **`GenerationRequest`** is a frozen dataclass containing the formatted system prompt, user prompt, conversation context, `channel_id`, and `participants` dict
- **`Config.save(field, value)`** updates both the in-memory field and the TOML file via `tomli_w`
- **`format_system_prompt()`** in `prompt.py` handles template formatting with persona name, examples, and memories
- **`store.get_sampled_messages()`** uses index-based tracking to avoid duplicates when balancing samples across source files
- **Scheduler** uses a plain `asyncio.Task` loop with persistent state in `scheduler_state.json`
- **Debouncing** in chat uses per-channel `asyncio.Task` cancellation
- **`remember_user`** tool uses display name (not user_id) since the LLM sees names in context, not IDs
- Both `enable_web_search` and `enable_memory` default to `false` — zero behavior change without opt-in
