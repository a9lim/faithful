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

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

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

You can also right-click any message and use the **Add to Persona** context menu to add it directly as an example message.

## How It Works

### Responding to Messages

The bot responds when mentioned or replied to. To prevent disjointed conversations, it ignores replies to messages older than 5 minutes (configurable).

### Message Processing

- **Debounce:** When you send a message, the bot waits for you to finish typing multiple messages.
- **Intelligent Chunking:** Responses are split by newlines, but long sentences are split at logical points (., !, ?) to maintain readability within Discord's 2000-char limit.
- **Natural Delay:** Simulates typing based on the length of each chunk.

### Spontaneous Messages

If `SPONTANEOUS_CHANNELS` is configured, the bot sends 1–2 unprompted messages per day at random intervals into one of those channels.

### Backends

- **Markov** — builds a statistical model from examples and generates text that mimics patterns. No external API needed but less coherent in conversation.
- **Ollama** — sends a system prompt with examples to a locally-running LLM. Requires [Ollama](https://ollama.com) with a model pulled (e.g., `ollama pull llama3`).
- **OpenAI** — uses the OpenAI Responses API. Set `OPENAI_BASE_URL` to point to alternative providers.
- **Gemini** — uses the Google Gemini API via the `google-genai` SDK. Requires a `GEMINI_API_KEY`.
- **Anthropic** — uses the Anthropic Messages API. Requires an `ANTHROPIC_API_KEY`. Handles message role alternation automatically.

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

The bot is configured via environment variables. See .env.example for a full list of available options.

### General Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Your Discord bot token | (Required) |
| `ADMIN_USER_ID` | Your Discord user ID | (Required) |
| `ADMIN_ONLY_UPLOAD` | If `True`, only the admin can upload/add messages | `True` |
| `PERSONA_NAME` | The name of the chatbot | `faithful` |
| `ACTIVE_BACKEND` | Text generation backend: `markov`, `ollama`, `openai`, `gemini`, or `anthropic` | `markov` |

### Backend-Specific Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | Ollama model name | `llama3` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI API key | |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | OpenAI-compatible API base URL | `https://api.openai.com/v1` |
| `GEMINI_API_KEY` | Google Gemini API key | |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.0-flash` |
| `ANTHROPIC_API_KEY` | Anthropic API key | |
| `ANTHROPIC_MODEL` | Anthropic model name | `claude-sonnet-4-20250514` |

### LLM Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_TEMPERATURE` | Controls randomness (0.0–2.0) | `1.0` |
| `LLM_MAX_TOKENS` | Maximum tokens per response | `1024` |
| `LLM_SAMPLE_SIZE` | How many example messages to feed the LLM | `300` |
| `SYSTEM_PROMPT_TEMPLATE` | Custom prompt for LLM backends | (See `config.py`) |

### Chat Behaviour

| Variable | Description | Default |
|----------|-------------|---------|
| `REPLY_PROBABILITY` | Chance of random unsolicited reply (0.0–1.0) | `0.02` |
| `DEBOUNCE_DELAY` | Seconds to wait for multi-message bursts | `3.0` |
| `CONVERSATION_EXPIRY` | Seconds before a thread is considered stale | `300.0` |
| `MAX_CONTEXT_MESSAGES` | Number of previous messages to include | `20` |

## Project Structure

```
faithful/
├── pyproject.toml            # Dependencies and project metadata
├── .env.example              # Environment variable template
├── .gitignore
├── README.md
└── faithful/                 # Main package
    ├── __main__.py           # Entry point
    ├── bot.py                # Discord bot class
    ├── config.py             # Configuration loader
    ├── store.py              # Example message storage
    ├── prompt.py             # Prompt assembly from channel state
    ├── chunker.py            # Message chunking and typing delays
    ├── backends/             # Text-generation backends
    │   ├── base.py           # GenerationRequest + abstract Backend
    │   ├── llm.py            # Shared logic for LLM backends
    │   ├── markov.py         # Markov chain (no API)
    │   ├── ollama_backend.py # Local LLM via Ollama
    │   ├── openai_backend.py # OpenAI Responses API
    │   ├── gemini_backend.py # Google Gemini
    │   └── anthropic_backend.py # Anthropic Claude
    └── cogs/                 # Discord command/event modules
        ├── admin.py          # Admin slash commands
        ├── chat.py           # Message handling & responses
        └── scheduler.py      # Spontaneous message scheduler
```

## License

AGPL :3
