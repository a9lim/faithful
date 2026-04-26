# Faithful

Faithful is a Discord bot that reads a corpus of example messages and emulates the author's tone and typing style. It responds when mentioned or replied to, and can optionally chime in on its own.

## Features

- **Message emulation**: learns from example messages you provide
- **Natural chat flow**: sends separate messages with typing-speed delays and chunking that prefers splitting at punctuation
- **Swappable backends**: pick one of:
  | Backend | Description | Requirements |
  |---------|-------------|-------------|
  | `openai-compatible` | Any OpenAI-compatible API via [Chat Completions](https://platform.openai.com/docs/api-reference/chat). Covers local servers like Ollama, LM Studio, and vLLM, plus most cloud providers. (default) | `base_url` (API key optional) |
  | `openai` | OpenAI cloud via the [Responses API](https://platform.openai.com/docs/api-reference/responses) | API key |
  | `gemini` | Google [Gemini](https://ai.google.dev/) | API key |
  | `anthropic` | [Anthropic Claude](https://docs.anthropic.com/) | API key |
- **Web search**: backends can search the web when they need current information. OpenAI, Gemini, and Anthropic use their providers' native server-side search; the OpenAI-compatible backend falls back to DuckDuckGo (opt-in)
- **Memory**: remembers facts about users and channels across conversations, injected into the system prompt (opt-in)
- **Reactions**: reacts to messages with emoji, including server custom emoji, both alongside replies and on its own
- **Spontaneous messaging**: optionally sends 1-2 unprompted messages per day into a configured channel
- **Random replies**: configurable chance of replying to any message, even when not pinged

## Prerequisites

- **Python 3.10+**
- A **Discord bot application** with the **Message Content** privileged intent enabled

## Quick Start

```bash
pip install "faithful[all]"     # core plus all three backend SDKs
faithful                        # run the interactive setup wizard
faithful run                    # start the bot
```

The wizard writes `~/.faithful/config.toml`. Run `faithful doctor` any time to check connectivity, or `faithful info` to see where things live.

If you want a slimmer install, the per-backend extras are `[openai]`, `[gemini]`, and `[anthropic]`. The OpenAI-compatible backend uses the `openai` package, so `[openai]` covers both. Override paths with `--config <path>`, `--data-dir <path>`, or set `FAITHFUL_HOME=/some/dir`.

## Commands

All commands are slash commands and only usable by users listed in `admin_ids`.

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
| `/memory list <target> [user]` | List memories for a user or channel |
| `/memory add <target> <text> [user]` | Add a memory for a user or channel |
| `/memory remove <target> <index> [user]` | Remove a memory by index |
| `/memory clear <target> [user]` | Clear all memories for a user or channel |

You can also right-click any message and use the **Add to Persona** context menu to add it directly as an example.

## How It Works

### Responding to messages

The bot responds when mentioned or replied to. To keep conversations from feeling disjointed, it ignores replies to messages older than 5 minutes (configurable).

### Message processing

- **Debounce**: when you send a message, the bot waits for you to finish typing multiple messages
- **Chunking**: responses are split by newlines, and long sentences are further split at sentence-ending punctuation (`.`, `!`, `?`) to stay under Discord's 2000-char limit
- **Natural delay**: simulates typing based on the length of each chunk

### Reactions

The bot can react to messages with emoji, including server custom emoji. Reactions happen in two ways:

- **With replies**: the LLM includes `[react: emoji]` markers in its response. The markers are stripped from the text and applied as reactions to the message being replied to.
- **Without replies**: controlled by `reaction_probability`, the bot may react to messages it doesn't reply to with a single emoji.

### Spontaneous messages

If `channels` is configured under `[scheduler]`, the bot sends 1-2 unprompted messages per day at random intervals into one of those channels.

### Backends

- **OpenAI**: uses the Responses API with native server-side web search.
- **OpenAI-compatible**: uses the Chat Completions API. Works with any compliant host, including local servers like Ollama (`base_url = "http://localhost:11434/v1"`), LM Studio, vLLM, text-generation-webui, and most cloud providers. Requires `base_url`. Falls back to DuckDuckGo for web search.
- **Gemini**: uses the Google Gemini API via the `google-genai` SDK, with `GoogleSearch` grounding for native search.
- **Anthropic**: uses the Messages API with streaming, prompt caching, and native server-side web search, web fetch, and code execution. The Anthropic-only knobs (`enable_thinking`, `enable_compaction`, `enable_1m_context`) are on by default and can be toggled in `[backend]`.

## Example Messages Format

### Text File (.txt)
Create a `.txt` file with one message per line:

```text
lol yeah thats what i was thinking
bruh no way
ok but have u considered... maybe not doing that
```

Upload via `/upload` or add individually with `/add_message`.

## Configuration

The bot is configured via `~/.faithful/config.toml`, generated by the wizard. The repo's `config.example.toml` documents every setting for power users who want to hand-edit. Environment variables override their TOML equivalents:

| Variable | Overrides |
|----------|-----------|
| `DISCORD_TOKEN` | `discord.token` |
| `ADMIN_USER_IDS` (comma-separated) | `discord.admin_ids` |
| `API_KEY` | `backend.api_key` |

The legacy `ADMIN_USER_ID` (singular) env var and `admin_user_id` TOML key are still supported as fallbacks.

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

AGPL :3
