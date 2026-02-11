# Faithy

A Discord bot that reads a corpus of example messages and emulates the author's tone, mannerisms, and typing style. It responds when mentioned, occasionally chimes in on its own, and sends 1–2 unprompted messages per day. 

## Features

- **Persona emulation** — learns from example messages you provide
- **Multi-file support** — upload and manage multiple `.txt` or `.json` example files
- **Natural chat flow** — separate message bubbles for newlines, typing-speed delays, and message debouncing
- **Swappable backends** — choose between:
  | Backend | Description | Requirements |
  |---------|-------------|-------------|
  | `markov` | Markov-chain text generation | None (default) |
  | `ollama` | Local LLM via [Ollama](https://ollama.com) | Ollama running locally |
  | `openai` | Cloud LLM (OpenAI, Groq, Together, etc.) | API key |
- **Conversation-aware** — tracks context with correct User/Assistant roles
- **Spontaneous messaging** — sends 1–2 unprompted messages per day
- **Random replies** — configurable chance of replying to any message

## Prerequisites

- **Python 3.10+**
- A **Discord bot application** with **Message Content** privileged intent enabled

## Quick Start

### 1. Clone and install

```bash
git clone <this-repo-url>
cd faithy
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
python -m faithy
```

## Commands

All commands are slash commands and only usable by the configured admin.

| Command | Description |
|---------|-------------|
| `/upload` | Upload a `.txt` or `.json` file of example messages |
| `/add_message <text>` | Add a single example message |
| `/list_messages [page]` | View stored messages (paginated) |
| `/remove_message <index>` | Remove a message by its index |
| `/clear_messages` | Remove all example messages |
| `/download_messages` | Download all messages as a `.txt` file |
| `/set_backend <backend>` | Switch backend: `markov`, `ollama`, or `openai` |
| `/status` | Show current configuration |

## How It Works

### Responding to Messages

The bot responds when mentioned or replied to. To prevent disjointed conversations, it ignores replies to messages older than 5 minutes (configurable).

### Message Processing

- **Debounce:** When you send a message, the bot waits 3 seconds (configurable) for you to finish typing multiple messages before it starts generating a response.
- **Multi-Message:** The bot splits its responses by newlines and sends them as separate messages with a natural typing delay.

### Spontaneous Messages

If `SPONTANEOUS_CHANNELS` is configured, the bot sends 1–2 unprompted messages per day at random intervals into one of those channels.

### Backends

- **Markov** — builds a statistical model from your examples and generates text that mimics patterns. No external API needed. Good for capturing typing quirks, but less coherent in conversation.
- **Ollama** — sends a system prompt (with your examples) to a locally-running LLM. Great balance of privacy and quality. Requires [Ollama](https://ollama.com) with a model pulled (e.g., `ollama pull llama3`).
- **OpenAI** — uses any OpenAI-compatible chat API. Best coherence. Set `OPENAI_BASE_URL` to point to alternative providers.

## Example Messages Format

### Text File (.txt)
Create a `.txt` file with one message per line:

```text
lol yeah thats what i was thinking
bruh no way
ok but have u considered... maybe not doing that
```

### JSON File (.json)
You can also upload a JSON array of strings:

```json
[
  "im literally gonna lose it 😭",
  "wait actually that kinda goes hard ngl"
]
```

Upload via `/upload` or add individually with `/add_message`.

## Project Structure

```
faithy/
├── pyproject.toml         # Dependencies and project metadata
├── .env.example           # Environment variable template
├── .gitignore
├── README.md
└── faithy/                # Main package
    ├── __init__.py
    ├── __main__.py        # Entry point
    ├── bot.py             # Discord bot class
    ├── config.py          # Configuration loader
    ├── store.py           # Example message storage
    ├── backends/          # Text-generation backends
    │   ├── __init__.py    # Backend factory
    │   ├── base.py        # Abstract base class
    │   ├── markov.py      # Markov chain (no API)
    │   ├── ollama_backend.py  # Local LLM via Ollama
    │   └── openai_backend.py  # Cloud LLM (OpenAI-compatible)
    └── cogs/              # Discord command/event modules
        ├── __init__.py
        ├── admin.py       # Admin slash commands
        ├── chat.py        # Message handling & responses
        └── scheduler.py   # Spontaneous message scheduler
```

## License

AGPL :3
