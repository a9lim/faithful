# Security Policy

## Reporting a vulnerability

If you found a security issue in faithful, please report it privately rather than filing a public issue.

- **Email:** mx@a9l.im
- **GitHub:** use [private security advisories](https://github.com/a9lim/faithful/security/advisories/new)

Please include a description, steps to reproduce, and the version you are on. I'll respond in a few days and try to have a fix as soon as possible.

## Supported versions

Only the latest release on PyPI gets security fixes. If you're on an older version, please upgrade.

## What faithful does at startup

A few things faithful does at startup touch your real environment.

- **Reads `config.toml`** from `~/.faithful/` (or `$FAITHFUL_HOME`). This file usually contains your Discord bot token and an LLM provider API key. Please keep it private.
- **Connects to Discord** with your bot token.
- **Connects to your chosen LLM provider** (OpenAI, Gemini, Anthropic, or any OpenAI-compatible host) with your API key.
- **Reads and writes plain files in `data/`** for the example corpus. If `[behavior] enable_memory` is on, the memory tool can also create, edit, and delete plain files in `data/memories/`. Path traversal outside that directory is blocked.
- **Makes outbound HTTP requests** if `[behavior] enable_web_search` is on. For OpenAI, Gemini, and Anthropic this happens server-side on the provider's infrastructure. For OpenAI-compatible backends faithful itself queries DuckDuckGo and then fetches whatever URLs the model asks for.

If you don't want any of this, please leave `enable_web_search` and `enable_memory` set to `false` (the defaults).

## What faithful does not do

- Rate limit incoming Discord messages.
- Restrict which URLs the model can fetch. 
- Sandbox the LLM provider's responses. 
- Vet who pings the bot.

## Admin commands

All Discord slash commands (`/upload`, `/add_message`, `/clear_messages`, `/memory`, `/status`, `/generate_test`, and the rest) are restricted to the user IDs listed in `[discord] admin_ids` in your config. 

## Model and provider trust

Faithful sends your example messages, conversation history, and (if memory is on) the memory file contents to whichever LLM provider you point it at. Please only configure providers you are ok with sharing that with. 
