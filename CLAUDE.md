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

All backends implement `Backend` (in `backends/base.py`) with `setup(examples)` and `generate(request)`. LLM backends extend `BaseLLMBackend` (`backends/llm.py`) — subclasses only implement `_call_api(system_prompt, messages)`.

Each LLM API handles system prompts differently:
- **OpenAI**: `"developer"` role in input messages (Responses API)
- **Ollama**: `"system"` role prepended to messages
- **Gemini**: `system_instruction` in `GenerateContentConfig`
- **Anthropic**: `system=` parameter (separate from messages), plus `_normalize_messages()` to enforce role alternation

Backends are registered in `backends/__init__.py` and instantiated via `get_backend(name, config)`.

### Key Design Decisions

- **`GenerationRequest`** is a frozen dataclass containing the formatted system prompt, user prompt, and conversation context
- **`Config.save(field, value)`** updates both the in-memory field and the TOML file via `tomli_w`
- **`format_system_prompt()`** in `prompt.py` handles template formatting with persona name and examples
- **`store.get_sampled_messages()`** uses index-based tracking to avoid duplicates when balancing samples across source files
- **Scheduler** uses a plain `asyncio.Task` loop with persistent state in `scheduler_state.json`
- **Debouncing** in chat uses per-channel `asyncio.Task` cancellation
