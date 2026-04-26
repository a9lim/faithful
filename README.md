# Faithful

[![CI](https://github.com/a9lim/faithful/actions/workflows/ci.yml/badge.svg)](https://github.com/a9lim/faithful/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/faithful)](https://pypi.org/project/faithful/)
[![Downloads](https://img.shields.io/pypi/dm/faithful)](https://pypi.org/project/faithful/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/faithful/)

Faithful is a Discord bot that reads example messages and mimics the author's tone and typing style. It responds when mentioned or replied to, and can optionally post on its own.

## Features

- **Swappable backends**:
  | Backend | Description | Requirements |
  |---------|-------------|-------------|
  | `openai-compatible` | Any OpenAI-compatible API via [Chat Completions](https://platform.openai.com/docs/api-reference/chat). (default) | `base_url` (API key optional) |
  | `openai` | [OpenAI](https://platform.openai.com/docs/api-reference/responses) | API key |
  | `gemini` | [Google Gemini](https://ai.google.dev/) | API key |
  | `anthropic` | [Anthropic Claude](https://docs.anthropic.com/) | API key |
- **Web search**: optionally searches the web for current information.
- **Memory**: optionally remembers facts about users and channels across conversations 
- **Reactions**: optionally reacts to messages with emojis including custom ones
- **Random posts**: optionally sends a few messages per day into a configured channel
- **Random replies**: optionally replies to any message at a configurable probability

## Prerequisites

- A **Discord bot** with the **Message Content** privileged intent enabled
- A LLM provider of your choice

## Quick Start

```bash
pip install "faithful[all]"     # core plus all three backend SDKs
faithful                        # run the interactive setup wizard
faithful run                    # start the bot
```

The wizard writes `~/.faithful/config.toml`. Run `faithful doctor` any time to check connectivity, or `faithful info` to see where things live.

If you want a slimmer install, the per-backend extras are `[openai]`, `[gemini]`, and `[anthropic]`. The OpenAI-compatible backend uses the `openai` package as well. Override paths with `--config <path>`, `--data-dir <path>`, or set `FAITHFUL_HOME=/some/dir`.

## Commands

The admin commands are slash commands restricted to users listed in `admin_ids`.

| Command | Description |
|---------|-------------|
| `/upload` | Upload a `.txt` file of example messages |
| `/add_message <text>` | Add a single example message |
| `/list_messages [page]` | View stored messages (paginated) |
| `/remove_message <index>` | Remove a message by its index |
| `/clear_messages` | Remove all example messages |
| `/download_messages` | Download all messages as a `.txt` file |
| `/generate_test <prompt>` | Manually trigger a response test |
| `/status` | Show detailed configuration status |

`/help` is available to anyone in the server and lists the commands above.

You can also right-click any message and use the **Add to Persona** context menu to add it directly as an example.

When `enable_memory` is on, the bot manages per-channel memory automatically through the LLM's memory tool. There are no memory slash commands.

## How It Works

The bot responds when mentioned, when replied to, when an active conversation is in progress, or randomly based on `reply_probability`. A reply to a bot message only counts as active if the original message is newer than `conversation_expiry` (default 300 seconds).

The bot can react to messages with emoji, including server custom emoji. Reactions happen in two ways: the LLM can include `[react: emoji]` markers at the end of a response, and on messages where the bot does not reply, it may still react based on `reaction_probability`.

If `channels` is configured under `[scheduler]`, the bot sends spontaneous messages at random intervals between `min_hours` and `max_hours` into one of those channels.

## Example Messages Format

Create a `.txt` file with one message per line:

```text
lol yeah thats what i was thinking
bruh no way
ok but have u considered... maybe not doing that
```

Upload via `/upload` or add individually with `/add_message`.

## Configuration

The bot is configured via `~/.faithful/config.toml`. The repo's `config.example.toml` documents every setting. Environment variables override their TOML equivalents:

| Variable | Overrides |
|----------|-----------|
| `DISCORD_TOKEN` | `discord.token` |
| `ADMIN_USER_IDS` (comma-separated) | `discord.admin_ids` |
| `API_KEY` | `backend.api_key` |

### `[discord]`

| Key | Description | Default |
|-----|-------------|---------|
| `token` | Your Discord bot token | (Required) |
| `admin_ids` | List of Discord user IDs who can manage the bot | (Required) |

### `[backend]`

| Key | Description | Default |
|-----|-------------|---------|
| `active` | Backend to use: `openai`, `openai-compatible`, `gemini`, `anthropic` | `openai-compatible` |
| `api_key` | API key for the active LLM backend | |
| `model` | Model name for the active LLM backend | (per-backend default) |
| `base_url` | Endpoint URL, required for `openai-compatible` (e.g. `http://localhost:11434/v1` for Ollama) | |

### `[llm]`

| Key | Description | Default |
|-----|-------------|---------|
| `temperature` | Controls randomness (0.0-2.0) | `1.0` |
| `max_tokens` | Maximum tokens per response | `16000` |
| `sample_size` | Example messages to include in the system prompt | `300` |

### `[behavior]`

| Key | Description | Default |
|-----|-------------|---------|
| `persona_name` | The persona name used in system prompts | `faithful` |
| `reply_probability` | Chance of random unsolicited reply (0.0-1.0) | `0.02` |
| `reaction_probability` | Chance of reacting to a message without replying (0.0-1.0) | `0.05` |
| `debounce_delay` | Seconds to wait for multi-message bursts | `3.0` |
| `conversation_expiry` | Seconds before a thread is considered stale | `300.0` |
| `max_context_messages` | Number of previous messages to include | `20` |
| `max_session_messages` | Per-channel session history window | `50` |
| `enable_web_search` | Allow the LLM to search the web | `false` |
| `enable_memory` | Enable per-user and per-channel memory | `false` |
| `system_prompt` | Custom system prompt template (`{name}`, `{examples}`, `{custom_emojis}` placeholders) | (built-in) |

### `[scheduler]`

| Key | Description | Default |
|-----|-------------|---------|
| `channels` | Channel IDs for unprompted messages | `[]` |
| `min_hours` | Minimum hours between spontaneous messages | `12` |
| `max_hours` | Maximum hours between spontaneous messages | `24` |

## Project Structure

```
faithful/
├── pyproject.toml              # dependencies and project metadata
├── config.example.toml         # reference config for hand-editors
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
└── faithful/                   # main package
    ├── cli.py                  # argparse entry point and verb dispatch
    ├── verbs.py                # `info` and `run` verbs
    ├── wizard.py               # interactive setup wizard
    ├── doctor.py               # connectivity self-check
    ├── bot.py                  # Discord bot class
    ├── config.py               # TOML config loader (read-only at runtime)
    ├── paths.py                # config and data directory resolution
    ├── errors.py               # friendly user-facing exceptions
    ├── store.py                # example message storage
    ├── prompt.py               # prompt assembly and custom emoji
    ├── chunker.py              # message chunking, typing delays, reaction parsing
    ├── tools/                  # tool definitions and executors
    │   ├── definitions.py      # provider-agnostic tool schemas
    │   ├── executor.py         # dispatch (web search, web fetch, memory)
    │   └── memory.py           # MemoryExecutor for the file-based memory tool
    ├── backends/               # text-generation backends
    │   ├── base.py             # Backend ABC, GenerationRequest, session history, tool loop
    │   ├── openai.py           # OpenAI Responses API
    │   ├── openai_compat.py    # OpenAI-compatible Chat Completions API
    │   ├── gemini.py           # Google Gemini
    │   └── anthropic.py        # Anthropic Claude
    └── cogs/                   # Discord command and event modules
        ├── admin.py            # admin slash commands and memory management
        ├── chat.py             # message handling, responses, reactions
        ├── onboarding.py       # welcome DM and `/help`
        └── scheduler.py        # spontaneous message scheduler
```

## License

AGPL-3.0-or-later. See LICENSE.
