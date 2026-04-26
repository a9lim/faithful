# Security Policy

## Reporting a vulnerability

If you've found a security issue in faithful, please report it privately rather than filing a public issue.

- **Email:** mx@a9l.im
- **GitHub:** use [private security advisories](https://github.com/a9lim/faithful/security/advisories/new)

Please include a description, steps to reproduce, and the version you are on. I'll respond within a few days and aim to have a fix as soon as possible.

## Supported versions

Only the latest release on PyPI receives security fixes. If you're on an older version, the fix is to upgrade.

## What faithful does at startup

A few things faithful does at startup touch your real environment, so it's worth knowing what they are.

- **Reads `config.toml`** from `~/.faithful/` (or `$FAITHFUL_HOME`). This file usually contains your Discord bot token and an LLM provider API key. Please keep it private.
- **Connects to Discord** with your bot token. Anyone with this token can impersonate your bot. If it leaks, please reset it from the Discord developer portal immediately.
- **Connects to your chosen LLM provider** (OpenAI, Gemini, Anthropic, or any OpenAI-compatible host) with the configured API key.
- **Reads and writes plain files in `data/`** for the example corpus. If `[behavior] enable_memory` is on, the memory tool can also create, edit, and delete plain files in `data/memories/`. Path traversal outside that directory is blocked.
- **Makes outbound HTTP requests** if `[behavior] enable_web_search` is on. For OpenAI, Gemini, and Anthropic this happens server-side on the provider's infrastructure. For OpenAI-compatible backends faithful itself queries DuckDuckGo and then fetches whatever URLs the model asks for.

If you don't want any of this, please leave `enable_web_search` and `enable_memory` set to `false` (the defaults).

## What faithful does not do

- Rate limit incoming Discord messages. The debounce timer groups bursts but does not throttle.
- Restrict which URLs the model can fetch. A jailbroken model on the OpenAI-compatible backend with web search on can ask faithful to retrieve arbitrary URLs from the bot's network.
- Sandbox the LLM provider's responses. The bot will type whatever the model tells it to type, so please choose providers and prompts you trust.
- Vet who pings the bot. Anyone in a server the bot is in can mention or DM it and trigger a generation, which costs you tokens. Slash commands are gated to `admin_ids`, but message replies are not.

## Admin commands

All slash commands (`/upload`, `/add_message`, `/clear_messages`, `/memory`, `/status`, `/generate_test`, and the rest) are gated to the user IDs listed in `[discord] admin_ids` in your config. If your admin list is wrong, those commands stop being safe; please double-check before deploying.

## Model and provider trust

Faithful sends your example messages, conversation history, and (if memory is on) the memory file contents to whichever LLM provider you point it at. Please only configure providers you're willing to share that data with. The OpenAI-compatible backend will happily talk to any host you give it a `base_url` for, including local Ollama instances or self-hosted vLLM servers.
