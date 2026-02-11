# Faithy — Discord Persona Chatbot

A Discord bot that reads a corpus of example messages and emulates the author's tone, mannerisms, and typing style. It responds when mentioned, occasionally chimes in on its own, and sends 1–2 unprompted messages per day. The text-generation backend is swappable at runtime.

## Features

- **Persona emulation** — learns from example messages you provide
- **Swappable backends** — choose between:
  | Backend | Description | Requirements |
  |---------|-------------|-------------|
  | `markov` | Markov-chain text generation | None (default) |
  | `ollama` | Local LLM via [Ollama](https://ollama.com) | Ollama running locally |
  | `openai` | Cloud LLM (OpenAI, Groq, Together, etc.) | API key |
- **Conversation-aware** — tracks recent channel messages for coherent replies
- **Spontaneous messaging** — sends 1–2 unprompted messages per day
- **Random replies** — configurable chance of replying to any message
- **Admin-only management** — only the configured admin can upload/modify examples and switch backends

## Prerequisites

- **Python 3.10+**
- A **Discord bot application** with:
  - Bot token
  - **Message Content** privileged intent enabled
  - Bot invited to your server with `bot` + `applications.commands` scopes

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

Edit `.env`:

```env
# Required
DISCORD_TOKEN=your-bot-token
ADMIN_USER_ID=your-discord-user-id

# Optional — defaults shown
ACTIVE_BACKEND=markov
REPLY_PROBABILITY=0.02
PERSONA_NAME=Faithy

# For spontaneous messages, add channel IDs:
SPONTANEOUS_CHANNELS=123456789,987654321

# If using Ollama:
OLLAMA_MODEL=llama3
OLLAMA_HOST=http://localhost:11434

# If using OpenAI-compatible API:
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

<details>
<summary><strong>How to find your Discord User ID</strong></summary>

1. Open Discord Settings → Advanced → enable **Developer Mode**
2. Right-click your username → **Copy User ID**

</details>

<details>
<summary><strong>How to create a Discord bot application</strong></summary>

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → give it a name → **Create**
3. Go to **Bot** → click **Reset Token** → copy the token into your `.env`
4. Under **Privileged Gateway Intents**, enable **Message Content Intent**
5. Go to **OAuth2** → **URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Read Message History`, `Use Slash Commands`
6. Copy the generated URL and open it in your browser to invite the bot

</details>

### 3. Run

```bash
python -m faithy
```

## Admin Commands

All commands are slash commands and only usable by the configured admin.

| Command | Description |
|---------|-------------|
| `/upload` | Upload a `.txt` file of example messages (one per line) |
| `/add_message <text>` | Add a single example message |
| `/list_messages [page]` | View stored messages (paginated) |
| `/remove_message <index>` | Remove a message by its index |
| `/clear_messages` | Remove all example messages |
| `/download_messages` | Download all messages as a `.txt` file |
| `/set_backend <backend>` | Switch backend: `markov`, `ollama`, or `openai` |
| `/status` | Show current configuration |

## How It Works

### Responding to Messages

The bot responds when:
1. **Mentioned** (`@Faithy`) or **replied to**
2. **Random chance** — with probability set by `REPLY_PROBABILITY` (default 2%)

### Spontaneous Messages

If `SPONTANEOUS_CHANNELS` is configured, the bot sends 1–2 unprompted messages per day at random intervals into one of those channels.

### Backends

- **Markov** — builds a statistical model from your examples and generates text that mimics patterns. No external API needed. Good for capturing typing quirks, but less coherent in conversation.
- **Ollama** — sends a system prompt (with your examples) to a locally-running LLM. Great balance of privacy and quality. Requires [Ollama](https://ollama.com) with a model pulled (e.g., `ollama pull llama3`).
- **OpenAI** — uses any OpenAI-compatible chat API. Best coherence. Set `OPENAI_BASE_URL` to point to alternative providers (Groq, Together, etc.).

## Example Messages Format

Create a `.txt` file with one message per line:

```text
lol yeah thats what i was thinking
bruh no way
ok but have u considered... maybe not doing that
im literally gonna lose it 😭
wait actually that kinda goes hard ngl
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

MIT
