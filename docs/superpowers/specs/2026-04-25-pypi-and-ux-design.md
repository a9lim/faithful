# PyPI Release & First-Run UX — Design

**Status:** approved
**Date:** 2026-04-25
**Target version:** 1.0.0 (first PyPI publish; resets internal 3.0.0 numbering)

## Goal

Make `faithful` installable from PyPI and turn `pip install faithful` → working bot
into a five-minute experience for someone who has never run it before. No manual
file editing, no hunting through Discord docs, no Python tracebacks on first
mistake.

## Non-goals

- No web admin dashboard.
- No Docker image (separate spec, future).
- No bundled demo persona / starter corpus (intentional: empty-state hint covers
  the gap).
- No migration logic for existing dev-branch users (no real users yet — the
  layout change is a clean break).
- No `--reconfigure` flag (rare path; users can delete `~/.faithful/config.toml`
  and re-run `faithful` if they want to redo the wizard).

## User stories

1. **New user, never touched it.** `pip install faithful` → `faithful` →
   wizard runs, asks for token / admin IDs / backend / API key → validates the
   key live → writes `~/.faithful/config.toml` → prints a one-click invite URL
   → user clicks → user runs `faithful run` → bot connects, joins a server,
   DMs the admin with a quickstart message → admin uses `/upload` → bot starts
   replying.

2. **User mis-edits config.toml after the fact.** They get
   `~/.faithful/config.toml:14:3: invalid TOML — expected '=' after key`
   instead of a Python traceback. They fix it. `faithful doctor` confirms.

3. **User forgets where config lives.** `faithful info` prints the resolved
   config path, data dir, env overrides applied, version, active backend.

4. **Power user runs two bots from one machine.** `FAITHFUL_HOME=/srv/bot-a
   faithful run` and `FAITHFUL_HOME=/srv/bot-b faithful run` — fully isolated
   dotdirs, no flag juggling.

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────┐
│ faithful (CLI entry point — argparse)                            │
│   ├── faithful           → wizard if no config, else friendly err│
│   ├── faithful run       → load config + run bot                 │
│   ├── faithful doctor    → load config + ping Discord + ping LLM │
│   ├── faithful info      → print resolved paths + version        │
│   └── --version          → at every level                        │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ├──→ paths.py        (resolution: --flag > FAITHFUL_HOME > ~/.faithful/)
                          ├──→ config.py       (now takes paths as args, not __file__-relative)
                          ├──→ wizard.py       (interactive setup, NEW)
                          ├──→ doctor.py       (diagnostics, NEW)
                          ├──→ errors.py       (FaithfulError hierarchy, NEW)
                          └──→ bot.py          (existing; gets data_dir injected)
                                  │
                                  └──→ cogs/onboarding.py  (welcome DM + /help, NEW)
```

## Components

### 1. `faithful/paths.py` (new)

Single source of truth for path resolution.

**Resolution order** (highest precedence wins):
1. `--config <path>` and `--data-dir <path>` CLI flags (passed in by the CLI
   layer)
2. `FAITHFUL_HOME` env var → `$FAITHFUL_HOME/config.toml` and
   `$FAITHFUL_HOME/data/`
3. Default: `~/.faithful/config.toml` and `~/.faithful/data/`

**Public API:**
```python
@dataclass(frozen=True)
class ResolvedPaths:
    home: Path           # ~/.faithful or $FAITHFUL_HOME or parent of --config
    config_path: Path    # the config.toml path
    data_dir: Path       # data directory

def resolve_paths(
    config_override: Path | None = None,
    data_dir_override: Path | None = None,
) -> ResolvedPaths: ...

def ensure_home_exists(paths: ResolvedPaths) -> None: ...  # mkdir -p, mode 0700
```

**Layout under home:**
```
~/.faithful/
  config.toml
  data/
    persona/                  # example messages corpus
    memories/
    scheduler_state.json
    seen_guilds.json          # NEW: dedupe welcome DMs across restarts
```

**Removed:** the two `Path(__file__).resolve().parent.parent` lines in
`config.py`. `Config.from_file()` now takes a path argument (no default
fallback inside the class), and `Config.data_dir` is set explicitly by the
caller, not by a `default_factory` lambda.

### 2. `faithful/__main__.py` & CLI surface

Switch to `argparse` with subparsers. Verb table:

| Invocation | Behavior |
|---|---|
| `faithful` (no args) | Resolve paths. If config doesn't exist → run wizard. If config exists → exit 1 with `"Already configured at <path>. Run 'faithful run' to start the bot."` |
| `faithful run` | Resolve paths → load config → start bot. Errors cleanly with `FaithfulConfigError` (`"No config found at <path>. Run 'faithful' to set up."`) if no config exists. |
| `faithful doctor` | Resolve paths → load config → ping Discord (validate token) → ping active LLM provider (cheapest call). Print checklist. Exit 0 if all pass, 1 otherwise. |
| `faithful info` | Resolve paths → print version, config path, data dir, env overrides applied (`FAITHFUL_HOME`, `DISCORD_TOKEN`, `API_KEY`, `ADMIN_USER_IDS`), active backend, model. No network calls. |
| `--version` | Print `faithful <version>` and exit. Available at every subparser level. |

**Global flags** (apply to all verbs): `--config <path>`, `--data-dir <path>`,
`--version`.

**Wizard-only flags:** `--quick` (skip invite URL print), `--no-validate`
(skip live API key test).

**Top-level dispatcher:**
```python
def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    paths = resolve_paths(args.config, args.data_dir)
    try:
        return dispatch(args, paths)
    except FaithfulError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
```

`FaithfulError` is the only exception that gets the friendly path; anything
else gets a real traceback (those are bugs).

### 3. `faithful/wizard.py` (new)

Interactive setup. Pure-stdin/stdout so it's testable via `monkeypatch.setattr`
on `builtins.input` and `getpass.getpass`.

**Flow:**

1. **Banner.** "This will set up your Faithful bot. Takes ~2 min. Press Ctrl+C
   any time to abort. Nothing is written until the end."
2. **Discord token.** Prompt: "Discord bot token (https://discord.com/developers/applications →
   your app → Bot → Reset Token):" — use `getpass.getpass()` so it doesn't echo.
3. **Admin user IDs.** Prompt: "Your Discord user ID(s), comma-separated. Enable
   Developer Mode in Discord → right-click your name → Copy User ID:" — parse
   into `list[int]`, error if any aren't ints.
4. **Backend.** Numbered menu:
   ```
   Choose a backend:
     1) openai            — OpenAI (GPT models)
     2) openai-compatible — Ollama, LM Studio, vLLM, any OpenAI-API-compatible server
     3) gemini            — Google Gemini
     4) anthropic         — Anthropic Claude
   ```
5. **Backend-specific prompts:**
   - openai: API key prompt with link to `https://platform.openai.com/api-keys`,
     default model `gpt-4o-mini`.
   - openai-compatible: `base_url` (required), API key (optional, "leave blank
     if your local server doesn't need one"), model name (no default).
   - gemini: API key with link to `https://aistudio.google.com/apikey`, default
     model `gemini-2.0-flash`.
   - anthropic: API key with link to `https://console.anthropic.com/settings/keys`,
     default model `claude-haiku-4-5`.
6. **Live validation** (skipped if `--no-validate`):
   - openai: `client.models.list()` with 5s timeout.
   - openai-compatible: `client.models.list()` against `base_url`, 5s timeout
     (skip if no API key + no clear way to ping).
   - gemini: `genai.Client(api_key=...).models.list()` with 5s timeout.
   - anthropic: `client.messages.create(max_tokens=1, ...)` with 5s timeout.
   - On failure: print provider's error message, offer "[r]etry, [s]kip
     validation, [q]uit?"
7. **Write config.** Render TOML with a hand-rolled writer (~6 fields; avoids
   adding a `tomli_w` dependency just for the wizard). File mode `0600`.
   Includes a header comment: `# Generated by 'faithful' on YYYY-MM-DD. Edit
   any field. Run 'faithful doctor' to test.`
8. **Print invite URL** (skipped if `--quick`):
   - Application ID extracted from token: tokens are `<base64-app-id>.<ts>.<hmac>`,
     `base64.urlsafe_b64decode(parts[0] + '==').decode()` gives the ID. (Fall
     back to "couldn't parse — visit https://discord.com/developers/applications
     and find your Application ID under General Information" if the parse fails.)
   - Permissions int: 274877966400 (`Send Messages | Read Message History |
     Add Reactions | Use External Emojis | View Channel`). To be reverified
     during implementation against current Discord docs.
   - Scopes: `bot+applications.commands`.
   - Final URL: `https://discord.com/api/oauth2/authorize?client_id=<app_id>&permissions=274877966400&scope=bot+applications.commands`.
9. **"You're done."** "Click the URL above to add the bot to a server. Then
   run `faithful run` to start it. Run `faithful doctor` any time to check
   health, or `faithful info` to see where things live."

### 4. `faithful/doctor.py` (new)

```python
async def run_doctor(config: Config) -> int: ...  # exit code
```

Sequential checks, each producing one line of output:

1. `✓ config loaded from <path>`
2. `✓ data dir at <path>` (or warn if it doesn't exist / not writable)
3. **Discord token check** — `discord.Client.login(token)` then `close()`. Wrap
   in 10s timeout. On `LoginFailure`: `✗ Discord: invalid token`. On timeout:
   `✗ Discord: connection timed out`.
4. **LLM provider check** — same per-backend calls as the wizard's live
   validation, with 10s timeout. On success: `✓ <backend>: <model> OK`.
5. **Memory dir check** (if `enable_memory`) — verify `data/memories/` is
   writable.
6. **Web search check** (if `enable_web_search` and not a native-search
   backend) — fire one DuckDuckGo query.

Exit 0 only if all checks pass. Otherwise exit 1.

### 5. `faithful/errors.py` (new)

```python
class FaithfulError(Exception): ...
class FaithfulConfigError(FaithfulError): ...
class FaithfulSetupError(FaithfulError): ...    # wizard problems
class FaithfulRuntimeError(FaithfulError): ...  # mid-run cleanly-surfaced failures
```

`Config.validate()` raises `FaithfulConfigError` instead of `ValueError`. The
TOML loader wrapper catches `tomllib.TOMLDecodeError` and re-raises as
`FaithfulConfigError(f"{path}:{e.lineno}:{e.colno}: invalid TOML — {e.msg}")`.

Friendly per-field messages where they help:
- Missing `discord.token` → `"Missing required field: discord.token. Edit ~/.faithful/config.toml or run 'faithful' to redo setup (delete the existing config first)."`
- Missing `discord.admin_ids` → similar.
- Missing API key for non-`openai-compatible` backend → similar.

### 6. `faithful/cogs/onboarding.py` (new)

**On `on_guild_join`:**
1. Load `seen_guilds.json` (set of guild IDs).
2. If guild ID is in the set, return.
3. For each `admin_id` in `config.discord.admin_ids`:
   - Try `bot.get_user(admin_id).send(welcome_text)`.
   - On `discord.Forbidden`: try posting `<@admin_id>\n<welcome_text>` in the
     first channel where `bot.guild_permissions.send_messages` is true. Track
     whether any path succeeded for this admin.
   - On total failure: `log.warning("Could not reach admin %d in guild %d", ...)`.
4. Add guild ID to the set, write back.

**Welcome text:**
```
Hey — I just joined <Guild>.

To teach me how you talk, run /upload with a .txt file of your messages, or
/add_message to add them one at a time. Run /help any time to see all
commands.
```

**`/help` slash command:**

Static embed, no admin gate (Discord enforces admin-only commands separately).
Grouped sections:
- **Corpus:** `/upload`, `/add_message`, `/list_messages`, `/remove_message`,
  `/clear_messages`, `/download_messages`
- **Memory:** `/memory list/add/remove/clear`
- **Diagnostics:** `/status`, `/generate_test`
- Footer: `Config & data live at ~/.faithful/ on the host. Run 'faithful info'
  on the host to see paths.`

### 7. Empty-state response (modify `cogs/chat.py`)

Before generation:
```python
if len(self.bot.store.messages) == 0:
    if message_is_direct_invocation:  # ping or reply, not random-chance
        await message.reply(EMPTY_STATE_TEXT)
    return  # skip generation; skip random-chance; skip burning credits
```

`EMPTY_STATE_TEXT`: `"I don't have any example messages to learn from yet. An
admin can use /upload or /add_message to teach me."`

Reactions via `_maybe_react()` keep working — the bot can still react to
random messages; that doesn't need a corpus.

### 8. `pyproject.toml` polish

```toml
[project]
name = "faithful"
version = "1.0.0"
description = "A Discord chatbot that emulates the tone and typing style of provided example messages."
readme = "README.md"
license = { file = "LICENSE" }
requires-python = ">=3.10"
keywords = ["discord", "discord-bot", "llm", "chatbot", "persona"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Framework :: AsyncIO",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU Affero General Public License v3",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Communications :: Chat",
]

[project.urls]
Homepage = "https://github.com/a9lim/faithful"
Repository = "https://github.com/a9lim/faithful"
Issues = "https://github.com/a9lim/faithful/issues"
```

(Repo URLs assumed `github.com/a9lim/faithful` — confirm during implementation.)

### 9. `--version`

`faithful/__init__.py`:
```python
from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("faithful")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"  # editable install before metadata exists
```

`argparse` parsers all add: `parser.add_argument("--version", action="version",
version=f"faithful {__version__}")`.

## Data flow — first-run lifecycle

```
$ pip install faithful
$ faithful
   │  resolve_paths() → ~/.faithful/config.toml (doesn't exist)
   │  no config → wizard.run()
   │      banner → token → admin_ids → backend → api_key → model
   │      → live validate (mock-safe) → write config → print invite URL
   │  exit 0
$ # user clicks invite URL, adds bot to a server
$ faithful run
   │  resolve_paths() → load config → start bot
   │  bot connects → on_guild_join fires → DM admin or fallback channel
   │  guild_id added to seen_guilds.json
   │  admin uses /upload → bot starts replying
```

## Error handling

Every error path that's user-facing routes through `FaithfulError`. The
`__main__` dispatcher catches and prints `error: <message>` to stderr (red if
tty, plain otherwise — use `sys.stderr.isatty()` for the gate). Bugs (anything
not `FaithfulError`) get a regular traceback, because those are bugs and
should look like bugs.

TOML syntax errors point at line/column. Missing-field errors include a
specific next-step suggestion. Wizard live-validation failures show the
provider's actual error and offer retry/skip/quit.

## Testing

New test files (pytest, no new infra):

- `tests/test_paths.py` — resolution order, default, env var, flag override.
  Uses `monkeypatch` for env, `tmp_path` for fake homes.
- `tests/test_wizard.py` — mock `builtins.input` + `getpass.getpass`. Asserts:
  writes correct TOML, masks token, handles bad backend choice, `--quick`
  skips invite URL, `--no-validate` skips API call. Mock provider clients;
  no real network.
- `tests/test_cli.py` — argparse routing: bare `faithful` w/o config →
  wizard; bare `faithful` w/ config → friendly error; `faithful run` w/o
  config → friendly error; `--version` at every level.
- `tests/test_errors.py` — `FaithfulConfigError` formatting; TOML syntax →
  `path:line:col: ...`; missing-field next-step hint present.
- `tests/test_doctor.py` — mocked Discord + LLM clients; checklist ordering;
  exit code on partial failure; timeout doesn't hang the test.
- `tests/test_onboarding.py` — `on_guild_join` DMs admin, falls back to
  channel on `Forbidden`, persists guild ID, doesn't re-fire on second join.
  Uses `AsyncMock` matching existing test style.

**Existing tests touched:**
- `tests/test_config.py` — update path expectations (no more `__file__`-relative
  paths). Inject paths via the new constructor signature.

**Coverage:** keep parity. Wizard's interactive prompts are highest-risk new
code; that gets the heaviest unit-testing.

## Implementation order (suggestion for the plan)

1. `paths.py` + refactor `config.py` to accept paths (foundation; everything
   depends on it).
2. `errors.py` + wire friendly errors into `Config.validate()` and the TOML
   loader.
3. CLI skeleton: `argparse` with verbs, `--config`/`--data-dir`/`--version`,
   dispatcher with `FaithfulError` catch.
4. `info` and `run` verbs (smallest, prove the dispatch works).
5. `wizard.py` + `doctor.py`.
6. `cogs/onboarding.py` (welcome DM + `/help`).
7. Empty-state response in `cogs/chat.py`.
8. `pyproject.toml` polish + version reset to 1.0.0.
9. Tests for everything above (interleaved with each step is fine — they're
   small and parallelizable).

## Open questions

- Repo URL in `[project.urls]` — confirm `github.com/a9lim/faithful` during
  implementation.
- Discord permissions integer 274877966400 — reverify the bits during
  implementation against current Discord OAuth docs.
