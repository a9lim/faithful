# Faithful Refactor Design

## Goals

- Remove dead code (Markov backend), simplify the backend hierarchy
- Make config file-driven (remove runtime save), support multiple admins
- Slash bloated admin commands down to corpus management + status
- Add reactions and custom emoji support
- Consolidate duplicated logic across backends

## 1. Architecture & File Structure

Merge `Backend` + `BaseLLMBackend` into one class since all backends are LLM backends now. Delete `markov.py` and `llm.py`. Rename backend files to drop the `_backend` suffix.

```
faithful/
├── __init__.py, __main__.py
├── bot.py
├── config.py
├── store.py
├── prompt.py
├── chunker.py
├── memory.py
├── tools.py
├── backends/
│   ├── __init__.py
│   ├── base.py           # merged Backend + BaseLLMBackend + Attachment + GenerationRequest
│   ├── openai.py
│   ├── openai_compat.py
│   ├── anthropic.py
│   ├── gemini.py
│   └── ollama.py
└── cogs/
    ├── __init__.py
    ├── chat.py
    ├── admin.py
    └── scheduler.py
```

`Attachment` gains a `b64` property. `Backend` gains a `_parse_json_args()` static helper.

## 2. Config System

- `admin_user_id: int` → `admin_ids: list[int]`, env var `ADMIN_USER_IDS` (comma-separated)
- Remove `Config.save()`, `_FIELD_TO_TOML`, and `tomli_w` dependency
- Default backend → `"openai-compatible"`
- Add `reaction_probability: float = 0.05`
- Remove `admin_only_upload` — one permission tier (admin or not)

## 3. Admin Commands

**Keep:** `/upload`, `/add_message`, `/list_messages`, `/remove_message`, `/clear_messages`, `/download_messages`, `/status`, `/generate_test`, "Add to Persona" context menu, `/memory` group.

**Remove:** `/set_backend`, `/set_temperature`, `/set_probability`, `/set_debounce`.

`is_admin()` checks list membership. `can_upload()` removed — all admins can manage corpus.

## 4. Reactions & Custom Emoji

**Response-parsing approach:**
- System prompt instructs the LLM to include `[react: emoji]` markers
- `chunker.py` strips markers before sending, returns them separately
- Chat cog applies reactions to the prompt message

**React without replying:**
- `reaction_probability` config (default 0.05)
- When not replying, roll against probability
- Lightweight generation: "React with a single emoji, or say PASS"
- Parse and apply

**Custom emoji:**
- Fetch guild emoji, inject names into system prompt as `{custom_emojis}`
- Bot uses them in text (`:emoji_name:`) and reactions
- `GenerationRequest` gains `guild_id: int = 0`

## 5. Backend Consolidation

- `Attachment.b64` property eliminates repeated base64 encoding
- `_parse_json_args()` on `Backend` centralizes JSON argument parsing
- `ToolCall` import at module level in `base.py`
- No forced merging of backends — API differences are genuine
