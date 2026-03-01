# Faithful

A Discord bot that reads a corpus of example messages and emulates the author's tone, mannerisms, and typing style. It responds when mentioned, and can optionally chime in on its own.

## Features

- **Message emulation** — learns from example messages you provide
- **Natural chat flow** — sends separate messages with typing-speed delays and intelligent chunking (prioritizes splitting at punctuation)
- **Swappable backends** — choose between:
  | Backend | Description | Requirements |
  |---------|-------------|-------------|
  | `ollama` | Local LLM via [Ollama](https://ollama.com) | Ollama running locally |
  | `openai` | Cloud LLM via [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) | API key |
  | `openai-compatible` | Any OpenAI-compatible API via [Chat Completions](https://platform.openai.com/docs/api-reference/chat) (default) | `base_url` (API key optional) |
  | `gemini` | Cloud LLM via [Google Gemini](https://ai.google.dev/) | API key |
  | `anthropic` | Cloud LLM via [Anthropic Claude](https://docs.anthropic.com/) | API key |
- **Web search** — LLM backends can search the web when they need current information (native server-side search for OpenAI, Anthropic, and Gemini; DuckDuckGo fallback for Ollama and openai-compatible) (opt-in)
- **Memory** — remembers facts about users and channels across conversations, injected into the system prompt (opt-in)
- **Reactions** — reacts to messages with emoji (including server custom emoji), both alongside replies and independently
- **Spontaneous messaging** — optionally sends 1-2 unprompted messages per day
- **Random replies** — configurable chance of replying to any message, even when not pinged

## Prerequisites

- **Python 3.10+**
- A **Discord bot application** with **Message Content** privileged intent enabled

## Quick Start

### 1. Clone and install

```bash
git clone <this-repo-url>
cd faithful
pip install .
```

Or install in development mode:

```bash
pip install -e .
```

### 2. Configure

Copy the example config and fill in your values:

```bash
cp config.example.toml config.toml
```

At minimum, set `token` and `admin_ids` under `[discord]`. To use an LLM backend, set `active`, `api_key`, and `model` under `[backend]`.

### 3. Run

```bash
python -m faithful
```

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

You can also right-click any message and use the **Add to Persona** context menu to add it directly as an example message.

## How It Works

### Responding to Messages

The bot responds when mentioned or replied to. To prevent disjointed conversations, it ignores replies to messages older than 5 minutes (configurable).

### Message Processing

- **Debounce:** When you send a message, the bot waits for you to finish typing multiple messages.
- **Intelligent Chunking:** Responses are split by newlines, but long sentences are split at logical points (., !, ?) to maintain readability within Discord's 2000-char limit.
- **Natural Delay:** Simulates typing based on the length of each chunk.

### Reactions

The bot can react to messages with emoji, including server custom emoji. Reactions happen in two ways:

- **With replies** — the LLM includes `[react: emoji]` markers in its response, which are stripped from the text and applied as reactions to the message being replied to.
- **Without replies** — controlled by `reaction_probability`, the bot may react to messages it doesn't reply to with a single emoji.

### Spontaneous Messages

If `channels` is configured under `[scheduler]`, the bot sends 1-2 unprompted messages per day at random intervals into one of those channels.

### Backends

- **Ollama** — sends a system prompt with examples to a locally-running LLM. Requires [Ollama](https://ollama.com) with a model pulled (e.g., `ollama pull llama3`).
- **OpenAI** — uses the OpenAI Responses API with native web search support.
- **OpenAI-compatible** — uses the standard Chat Completions API. Works with LM Studio, vLLM, text-generation-webui, and other OpenAI-compatible providers. Requires `base_url`.
- **Gemini** — uses the Google Gemini API via the `google-genai` SDK.
- **Anthropic** — uses the Anthropic Messages API. Handles message role alternation automatically.

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

The bot is configured via `config.toml` (read-only at runtime). See `config.example.toml` for a full reference. Environment variables override their TOML equivalents:

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
| `active` | Backend to use: `ollama`, `openai`, `openai-compatible`, `gemini`, `anthropic` | `openai-compatible` |
| `api_key` | API key for the active LLM backend | |
| `model` | Model name for the active LLM backend | (per-backend default) |
| `base_url` | API endpoint for `openai-compatible` backend (required) | |
| `host` | Ollama server address | `http://localhost:11434` |

### `[llm]`

| Key | Description | Default |
|-----|-------------|---------|
| `temperature` | Controls randomness (0.0-2.0) | `1.0` |
| `max_tokens` | Maximum tokens per response | `1024` |
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
| `enable_web_search` | Allow the LLM to search the web | `false` |
| `enable_memory` | Enable per-user and per-channel memory | `false` |
| `system_prompt` | Custom system prompt template (`{name}`, `{examples}`, `{memories}`, `{custom_emojis}` placeholders) | (built-in) |

### `[scheduler]`

| Key | Description | Default |
|-----|-------------|---------|
| `channels` | Channel IDs for unprompted messages | `[]` |
| `min_hours` | Minimum hours between spontaneous messages | `12` |
| `max_hours` | Maximum hours between spontaneous messages | `24` |

## Project Structure

```
faithful/
├── pyproject.toml              # Dependencies and project metadata
├── config.example.toml         # Configuration template
├── .gitignore
├── README.md
└── faithful/                   # Main package
    ├── __main__.py             # Entry point
    ├── bot.py                  # Discord bot class
    ├── config.py               # TOML configuration loader (read-only)
    ├── store.py                # Example message storage
    ├── prompt.py               # Prompt assembly, system prompt, custom emoji
    ├── chunker.py              # Message chunking, typing delays, reaction parsing
    ├── memory.py               # Per-user and per-channel memory store
    ├── tools.py                # Tool definitions and executor (web search, memory)
    ├── backends/               # Text-generation backends
    │   ├── base.py             # Backend ABC, GenerationRequest, Attachment, ToolCall
    │   ├── ollama.py           # Local LLM via Ollama
    │   ├── openai.py           # OpenAI Responses API
    │   ├── openai_compat.py    # OpenAI-compatible Chat Completions API
    │   ├── gemini.py           # Google Gemini
    │   └── anthropic.py        # Anthropic Claude
    └── cogs/                   # Discord command/event modules
        ├── admin.py            # Admin slash commands and memory management
        ├── chat.py             # Message handling, responses, and reactions
        └── scheduler.py        # Spontaneous message scheduler
```

## License

AGPL :3
