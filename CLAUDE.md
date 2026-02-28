# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
pip install .              # install dependencies
cp .env.example .env       # configure (DISCORD_TOKEN and ADMIN_USER_ID required)
python -m faithful         # run
```

For development: `pip install -e .`

There is no test suite, linter, or CI pipeline configured.

## Architecture

Faithful is a Discord bot that emulates a persona by learning from example messages. It uses discord.py's cog system and a pluggable backend architecture.

### Request Flow

1. **`cogs/chat.py`** receives a Discord message, decides whether to respond (mention, reply, active conversation, or random chance), and starts a debounced task
2. **`prompt.py`** assembles a `GenerationRequest` from channel history — slicing from the last @mention, separating context from the triggering message, and sampling example messages from the store
3. The active **backend** generates a response from the `GenerationRequest`
4. **`chunker.py`** splits the response into Discord-safe chunks (<=2000 chars) and sends them with simulated typing delays

### Backend System

All backends implement `Backend` (in `backends/base.py`) with `setup(examples)` and `generate(request: GenerationRequest)`. LLM backends extend `BaseLLMBackend` (`backends/llm.py`) which handles system prompt formatting and message assembly — subclasses only implement `_call_api(system_prompt, messages)`.

Each LLM API handles system prompts differently:
- **OpenAI**: `"developer"` role in input messages (Responses API)
- **Ollama**: `"system"` role prepended to messages
- **Gemini**: `system_instruction` in `GenerateContentConfig`
- **Anthropic**: `system=` parameter (separate from messages), plus `_normalize_messages()` to enforce role alternation

Backends are registered in `backends/__init__.py` and instantiated via `get_backend(name, config)`.

### Key Design Decisions

- **`GenerationRequest`** is a frozen dataclass — backends receive all context in one object rather than positional args
- **`config.update_env()`** writes to `.env` and updates the in-memory field via `_ENV_TO_FIELD` mapping
- **`store.get_sampled_messages()`** uses index-based tracking to avoid duplicates when balancing samples across source files
- **Scheduler** uses a plain `asyncio.Task` loop (not `tasks.loop`) with persistent state in `scheduler_state.json`
- **Debouncing** in chat uses per-channel `asyncio.Task` cancellation — a new message cancels the pending task and starts a fresh one
