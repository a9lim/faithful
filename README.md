# Faithful

A Discord bot that reads a corpus of example messages and emulates the author's tone, mannerisms, and typing style. It responds when mentioned, and can optionally chime in on its own.

## Features

- **Message emulation** — learns from example messages you provide
- **Natural chat flow** — sends separate messages with typing-speed delays and intelligent chunking (prioritizes splitting at punctuation)
- **Swappable backends** — choose between:
  | Backend | Description | Requirements |
  |---------|-------------|-------------|
  | `markov` | Markov-chain text generation | None (default) |
  | `ollama` | Local LLM via [Ollama](https://ollama.com) | Ollama running locally |
  | `openai` | Cloud LLM via [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) | API key |
  | `gemini` | Cloud LLM via [Google Gemini](https://ai.google.dev/) | API key |
  | `anthropic` | Cloud LLM via [Anthropic Claude](https://docs.anthropic.com/) | API key |
- **Web search** — LLM backends can search the web via DuckDuckGo when they need current information (opt-in)
- **Memory** — remembers facts about users and channels across conversations, injected into the system prompt (opt-in)
- **Spontaneous messaging** — optionally sends 1–2 unprompted messages per day
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

At minimum, set `token` and `admin_user_id` under `[discord]`. To use an LLM backend, set `active`, `api_key`, and `model` under `[backend]`.

### 3. Run

```bash
python -m faithful
```

## Commands

All commands are slash commands and only usable by the configured admin.

| Command | Description |
|---------|-------------|
| `/upload` | Upload a `.txt` file of example messages |
| `/add_message <text>` | Add a single example message |
| `/list_messages [page]` | View stored messages (paginated) |
| `/remove_message <index>` | Remove a message by its index |
| `/clear_messages` | Remove all example messages |
| `/download_messages` | Download all messages as a `.txt` file |
| `/set_backend <backend>` | Switch backend: `markov`, `ollama`, `openai`, `gemini`, or `anthropic` |
| `/set_probability <value>` | Set random reply probability (0.0–1.0) |
| `/set_temperature <value>` | Set LLM temperature (0.0–2.0) |
| `/set_debounce <value>` | Set debounce delay in seconds |
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

### Spontaneous Messages

If `channels` is configured under `[scheduler]`, the bot sends 1–2 unprompted messages per day at random intervals into one of those channels.

### Backends

- **Markov** — builds a statistical model from examples and generates text that mimics patterns. No external API needed but less coherent in conversation.
- **Ollama** — sends a system prompt with examples to a locally-running LLM. Requires [Ollama](https://ollama.com) with a model pulled (e.g., `ollama pull llama3`).
- **OpenAI** — uses the OpenAI Responses API. Set `base_url` under `[backend]` to point to alternative providers.
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

The bot is configured via `config.toml`. See `config.example.toml` for a full reference. Environment variables `DISCORD_TOKEN`, `ADMIN_USER_ID`, and `API_KEY` can override their TOML equivalents.

### `[discord]`

| Key | Description | Default |
|-----|-------------|---------|
| `token` | Your Discord bot token | (Required) |
| `admin_user_id` | Your Discord user ID | (Required) |
| `admin_only_upload` | Only the admin can upload/add messages | `true` |

### `[backend]`

| Key | Description | Default |
|-----|-------------|---------|
| `active` | Backend to use: `markov`, `ollama`, `openai`, `gemini`, `anthropic` | `markov` |
| `api_key` | API key for the active LLM backend | |
| `model` | Model name for the active LLM backend | (per-backend default) |
| `base_url` | Custom base URL for OpenAI-compatible APIs | |
| `host` | Ollama server address | `http://localhost:11434` |

### `[llm]`

| Key | Description | Default |
|-----|-------------|---------|
| `temperature` | Controls randomness (0.0–2.0) | `1.0` |
| `max_tokens` | Maximum tokens per response | `1024` |
| `sample_size` | Example messages to include in the system prompt | `300` |

### `[behavior]`

| Key | Description | Default |
|-----|-------------|---------|
| `persona_name` | The persona name used in system prompts | `faithful` |
| `reply_probability` | Chance of random unsolicited reply (0.0–1.0) | `0.02` |
| `debounce_delay` | Seconds to wait for multi-message bursts | `3.0` |
| `conversation_expiry` | Seconds before a thread is considered stale | `300.0` |
| `max_context_messages` | Number of previous messages to include | `20` |
| `enable_web_search` | Allow LLM to search the web via DuckDuckGo | `false` |
| `enable_memory` | Enable per-user and per-channel memory | `false` |
| `system_prompt` | Custom system prompt template (`{name}`, `{examples}`, `{memories}` placeholders) | (built-in) |

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
    ├── config.py               # TOML configuration loader
    ├── store.py                # Example message storage
    ├── prompt.py               # Prompt assembly and system prompt formatting
    ├── chunker.py              # Message chunking and typing delays
    ├── memory.py               # Per-user and per-channel memory store
    ├── tools.py                # Tool definitions and executor (web search, memory)
    ├── backends/               # Text-generation backends
    │   ├── base.py             # GenerationRequest + abstract Backend
    │   ├── llm.py              # Shared logic for LLM backends (incl. tool loop)
    │   ├── markov.py           # Markov chain (no API)
    │   ├── ollama_backend.py   # Local LLM via Ollama
    │   ├── openai_backend.py   # OpenAI Responses API
    │   ├── gemini_backend.py   # Google Gemini
    │   └── anthropic_backend.py # Anthropic Claude
    └── cogs/                   # Discord command/event modules
        ├── admin.py            # Admin slash commands
        ├── chat.py             # Message handling & responses
        └── scheduler.py        # Spontaneous message scheduler
```

## License

AGPL :3
