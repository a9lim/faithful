# PyPI Release & First-Run UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship faithful 1.0.0 to PyPI with a frictionless first-run experience: `~/.faithful/` home dir, interactive wizard, friendly errors, welcome DM, `/help` command, doctor + info verbs.

**Architecture:** New foundation modules (`paths.py`, `errors.py`) own filesystem and exception concerns. New CLI module (`cli.py`) replaces the bare `__main__.py` with argparse subcommands. New `wizard.py` and `doctor.py` implement the new verbs. New `cogs/onboarding.py` handles guild-join welcome DMs and `/help`. `config.py` and `store.py` are refactored to receive paths from the caller instead of computing them from `__file__`.

**Tech Stack:** Python 3.10+, argparse, discord.py 2.3+, tomllib (stdlib) / tomli (3.10 fallback), pytest, pytest-asyncio, importlib.metadata.

**Spec:** `docs/superpowers/specs/2026-04-25-pypi-and-ux-design.md`

---

## File Structure

**New files:**

| Path | Responsibility |
|---|---|
| `faithful/paths.py` | Resolve config and data paths from CLI flags / env / default |
| `faithful/errors.py` | `FaithfulError` hierarchy |
| `faithful/cli.py` | Argparse, verb dispatch, friendly error printing |
| `faithful/wizard.py` | Interactive setup flow + invite URL builder + TOML writer |
| `faithful/doctor.py` | Diagnostic checks (config, Discord, LLM provider) |
| `faithful/cogs/onboarding.py` | `on_guild_join` welcome DM + `/help` slash command |
| `tests/test_paths.py` | Path resolution unit tests |
| `tests/test_errors.py` | Error formatting tests |
| `tests/test_cli.py` | Argparse routing tests |
| `tests/test_wizard.py` | Wizard prompt + writer + invite URL tests |
| `tests/test_doctor.py` | Doctor checklist tests with mocked clients |
| `tests/test_onboarding.py` | Welcome DM + /help tests |

**Modified files:**

| Path | Change |
|---|---|
| `faithful/__init__.py` | Add `__version__` from package metadata |
| `faithful/__main__.py` | Reduce to `from .cli import main; raise SystemExit(main())` |
| `faithful/config.py` | Drop `__file__`-relative paths; accept paths from caller; raise `FaithfulConfigError` |
| `faithful/store.py` | Use `config.data_dir / "persona"` (was `config.data_dir`) |
| `faithful/cogs/chat.py` | Replace silent return on empty corpus with empty-state reply |
| `tests/test_config.py` | Update to inject paths instead of relying on `__file__` |
| `pyproject.toml` | Version 1.0.0, classifiers, project URLs, keywords, license metadata |

---

## Task 1: Add `errors.py` with `FaithfulError` hierarchy

**Why first:** every later module raises these. Zero dependencies.

**Files:**
- Create: `faithful/errors.py`
- Create: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_errors.py`:
```python
"""Tests for the FaithfulError hierarchy."""
from faithful.errors import (
    FaithfulError,
    FaithfulConfigError,
    FaithfulSetupError,
    FaithfulRuntimeError,
)


def test_all_subclasses_inherit_from_faithful_error():
    assert issubclass(FaithfulConfigError, FaithfulError)
    assert issubclass(FaithfulSetupError, FaithfulError)
    assert issubclass(FaithfulRuntimeError, FaithfulError)


def test_faithful_error_is_an_exception():
    assert issubclass(FaithfulError, Exception)


def test_message_round_trips():
    err = FaithfulConfigError("missing token")
    assert str(err) == "missing token"
```

- [ ] **Step 2: Run the tests to confirm failure**

```
pytest tests/test_errors.py -v
```
Expected: collection error (`ModuleNotFoundError: No module named 'faithful.errors'`).

- [ ] **Step 3: Implement `faithful/errors.py`**

```python
"""Exception hierarchy for user-facing errors.

`__main__` catches `FaithfulError` and prints a friendly one-line message
instead of a traceback. Anything that is *not* a `FaithfulError` is treated
as a bug and propagates normally.
"""
from __future__ import annotations


class FaithfulError(Exception):
    """Base class for all user-facing faithful errors."""


class FaithfulConfigError(FaithfulError):
    """Config file missing, malformed, or failing validation."""


class FaithfulSetupError(FaithfulError):
    """Wizard could not complete setup (e.g. invalid token, write failed)."""


class FaithfulRuntimeError(FaithfulError):
    """Mid-run failure that should be surfaced cleanly to the user."""
```

- [ ] **Step 4: Run the tests to confirm pass**

```
pytest tests/test_errors.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add faithful/errors.py tests/test_errors.py
git commit -m "feat: add FaithfulError exception hierarchy"
```

---

## Task 2: Add `paths.py` for resolution logic

**Files:**
- Create: `faithful/paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paths.py`:
```python
"""Tests for path resolution."""
from pathlib import Path

import pytest

from faithful.paths import ResolvedPaths, ensure_home_exists, resolve_paths


def test_default_uses_home_faithful(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FAITHFUL_HOME", raising=False)

    paths = resolve_paths()

    assert paths.home == tmp_path / ".faithful"
    assert paths.config_path == tmp_path / ".faithful" / "config.toml"
    assert paths.data_dir == tmp_path / ".faithful" / "data"


def test_faithful_home_env_overrides_default(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "homedir")
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path / "envhome"))

    paths = resolve_paths()

    assert paths.home == tmp_path / "envhome"
    assert paths.config_path == tmp_path / "envhome" / "config.toml"
    assert paths.data_dir == tmp_path / "envhome" / "data"


def test_config_flag_overrides_env_and_default(monkeypatch, tmp_path):
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path / "envhome"))

    custom = tmp_path / "custom.toml"
    paths = resolve_paths(config_override=custom)

    assert paths.config_path == custom
    # data_dir falls back to env home when only --config is given
    assert paths.data_dir == tmp_path / "envhome" / "data"


def test_data_dir_flag_overrides_env_and_default(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FAITHFUL_HOME", raising=False)

    custom = tmp_path / "datasomewhere"
    paths = resolve_paths(data_dir_override=custom)

    assert paths.data_dir == custom
    assert paths.config_path == tmp_path / ".faithful" / "config.toml"


def test_ensure_home_creates_directory(tmp_path):
    paths = ResolvedPaths(
        home=tmp_path / ".faithful",
        config_path=tmp_path / ".faithful" / "config.toml",
        data_dir=tmp_path / ".faithful" / "data",
    )

    ensure_home_exists(paths)

    assert paths.home.is_dir()
    assert paths.data_dir.is_dir()
```

- [ ] **Step 2: Run the tests to confirm failure**

```
pytest tests/test_paths.py -v
```
Expected: collection error (no module).

- [ ] **Step 3: Implement `faithful/paths.py`**

```python
"""Resolve config and data paths for the faithful runtime.

Resolution order (highest precedence wins):
1. Explicit ``--config`` and ``--data-dir`` overrides passed by the CLI layer.
2. ``FAITHFUL_HOME`` environment variable -> ``$FAITHFUL_HOME/config.toml``
   and ``$FAITHFUL_HOME/data/``.
3. Default: ``~/.faithful/config.toml`` and ``~/.faithful/data/``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedPaths:
    """The resolved on-disk locations for one faithful instance."""

    home: Path
    config_path: Path
    data_dir: Path


def _home_root() -> Path:
    env = os.environ.get("FAITHFUL_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".faithful"


def resolve_paths(
    config_override: Path | None = None,
    data_dir_override: Path | None = None,
) -> ResolvedPaths:
    """Return the ResolvedPaths for this invocation."""
    home = _home_root()
    config_path = config_override if config_override is not None else home / "config.toml"
    data_dir = data_dir_override if data_dir_override is not None else home / "data"
    return ResolvedPaths(home=home, config_path=config_path, data_dir=data_dir)


def ensure_home_exists(paths: ResolvedPaths) -> None:
    """Create the home and data directories with mode 0700 if missing."""
    paths.home.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
```

- [ ] **Step 4: Run the tests to confirm pass**

```
pytest tests/test_paths.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add faithful/paths.py tests/test_paths.py
git commit -m "feat: resolve config and data paths under ~/.faithful by default"
```

---

## Task 3: Refactor `config.py` to accept paths and raise `FaithfulConfigError`

**Files:**
- Modify: `faithful/config.py` (remove `_CONFIG_PATH` module global; remove `__file__`-relative `data_dir` default; change `from_file` signature; raise `FaithfulConfigError`)
- Modify: `tests/test_config.py` (callers must pass `path=` and `data_dir=` explicitly)

- [ ] **Step 1: Update `tests/test_config.py` first to capture the new contract**

Read the current file, then change every `Config.from_file()` call site to pass an explicit path. Add three new tests at the end of the file that lock in the new behavior:

```python
# Append to tests/test_config.py

import pytest

from faithful.errors import FaithfulConfigError


def test_from_file_requires_explicit_path_and_data_dir(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[discord]\ntoken = "x"\nadmin_ids = [1]\n'
        '[backend]\napi_key = "k"\nmodel = "m"\n'
    )
    data_dir = tmp_path / "data"

    cfg = Config.from_file(config_path, data_dir=data_dir)

    assert cfg.data_dir == data_dir
    assert cfg.discord.token == "x"
    assert cfg.discord.admin_ids == [1]


def test_from_file_raises_faithful_config_error_on_bad_toml(tmp_path):
    bad = tmp_path / "config.toml"
    bad.write_text("[discord\ntoken = 'x'\n")

    with pytest.raises(FaithfulConfigError) as exc:
        Config.from_file(bad, data_dir=tmp_path / "data")

    msg = str(exc.value)
    assert str(bad) in msg
    assert ":" in msg  # contains line:col


def test_validate_raises_faithful_config_error_with_next_step(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("")
    cfg = Config.from_file(config_path, data_dir=tmp_path / "data")

    with pytest.raises(FaithfulConfigError) as exc:
        cfg.validate()

    msg = str(exc.value)
    assert "discord.token" in msg
    assert "faithful" in msg  # mentions the CLI as a next step
```

Also adjust any *existing* tests in `test_config.py` that call `Config.from_file()` with no args — pass an explicit `path` and `data_dir` (use `tmp_path`).

- [ ] **Step 2: Run the tests to confirm failure**

```
pytest tests/test_config.py -v
```
Expected: failures because the current `Config.from_file()` does not accept `data_dir=` and does not raise `FaithfulConfigError`.

- [ ] **Step 3: Refactor `faithful/config.py`**

Apply the following diffs (paste verbatim):

**Replace** the import block + `_CONFIG_PATH` line at the top:
```python
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from .errors import FaithfulConfigError

log = logging.getLogger("faithful.config")
```

(Delete the line `_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"`.)

**Replace** the `data_dir` field in `Config` and the body of `from_file`/`validate`:

```python
@dataclass
class Config:
    """Bot-wide configuration loaded from config.toml with env var overrides for secrets."""

    discord: DiscordConfig = field(default_factory=DiscordConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)

    data_dir: Path = field(default_factory=Path)  # required; supplied by caller

    @classmethod
    def from_file(cls, path: Path, *, data_dir: Path) -> "Config":
        """Load configuration from a TOML file. Raises FaithfulConfigError on parse errors."""
        raw = _load_toml(path)
        raw = _migrate_legacy_keys(raw)

        config = cls(data_dir=data_dir)
        _merge_dataclass(config, raw)

        config.discord.__post_init__()
        config.backend.__post_init__()
        config.llm.__post_init__()
        config.behavior.__post_init__()

        return config

    def __post_init__(self) -> None:
        # data_dir creation happens lazily — caller decides when (e.g. only on `run`)
        pass

    def validate(self) -> None:
        """Validate that required fields are present. Raises FaithfulConfigError."""
        if not self.discord.token:
            raise FaithfulConfigError(
                "Missing required field: discord.token. "
                "Edit ~/.faithful/config.toml or run 'faithful' to redo setup "
                "(delete the existing config first)."
            )
        if not self.discord.admin_ids:
            raise FaithfulConfigError(
                "Missing required field: discord.admin_ids. "
                "Add your Discord user ID(s) to ~/.faithful/config.toml."
            )
        if self.backend.active != "openai-compatible" and not self.backend.api_key:
            raise FaithfulConfigError(
                f"Missing API key for backend '{self.backend.active}'. "
                "Set backend.api_key in ~/.faithful/config.toml or the API_KEY env var."
            )
```

**Replace** `_load_toml` to raise `FaithfulConfigError` on TOML errors:

```python
def _load_toml(path: Path) -> dict:
    if not path.exists():
        raise FaithfulConfigError(
            f"No config found at {path}. Run 'faithful' to set up, or pass --config <path>."
        )
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        # tomllib's error message looks like "Invalid statement (at line 3, column 5)"
        # so we just include the original message verbatim with the path prefix.
        raise FaithfulConfigError(f"{path}: invalid TOML — {e}") from e
```

- [ ] **Step 4: Run the tests to confirm pass**

```
pytest tests/test_config.py tests/test_errors.py tests/test_paths.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```
git add faithful/config.py tests/test_config.py
git commit -m "refactor: config takes explicit paths; raises FaithfulConfigError"
```

---

## Task 4: Move persona corpus to `data/persona/` in `store.py`

**Files:**
- Modify: `faithful/store.py` (line 19)
- Modify: `tests/test_store.py` (existing tests that point at `data_dir` directly)

- [ ] **Step 1: Update `tests/test_store.py` to expect the persona subdir**

`tests/test_store.py` already has a helper:
```python
def _make_config(data_dir: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.data_dir = data_dir
    return cfg
```

Existing tests write text files to `tmp_path` directly (e.g. `(tmp_path / "msgs.txt").write_text(...)`) and expect the store to read from there. After the refactor, the store reads from `tmp_path / "persona"` instead. Update every fixture write that targets `tmp_path / "*.txt"` to target `tmp_path / "persona" / "*.txt"` (creating the persona dir first with `(tmp_path / "persona").mkdir()`).

Then add this new test at the end of the file:
```python
class TestPersonaSubdir:
    def test_store_writes_under_persona_subdir(self, tmp_path: Path):
        store = MessageStore(_make_config(tmp_path))
        store.add_messages(["hello"])
        assert (tmp_path / "persona" / "messages.txt").exists()
```

- [ ] **Step 2: Run the tests to confirm failure**

```
pytest tests/test_store.py -v
```
Expected: failures — current store writes to `data_dir` root.

- [ ] **Step 3: Modify `faithful/store.py`**

Change line 19 from:
```python
self._dir: Path = config.data_dir
```
to:
```python
self._dir: Path = config.data_dir / "persona"
```

(`reload()` already calls `self._dir.mkdir(parents=True, exist_ok=True)`, so the subdir is created on first access.)

- [ ] **Step 4: Run the tests to confirm pass**

```
pytest tests/test_store.py -v
```
Expected: green.

- [ ] **Step 5: Commit**

```
git add faithful/store.py tests/test_store.py
git commit -m "refactor: store persona corpus under data/persona/ subdir"
```

---

## Task 5: Add `__version__` to `faithful/__init__.py`

**Files:**
- Modify: `faithful/__init__.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_errors.py` (cheap reuse — no new test file):

```python
def test_version_is_a_string():
    import faithful

    assert isinstance(faithful.__version__, str)
    assert faithful.__version__  # non-empty
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_errors.py::test_version_is_a_string -v
```
Expected: `AttributeError: module 'faithful' has no attribute '__version__'`.

- [ ] **Step 3: Implement**

Replace `faithful/__init__.py` with:
```python
"""faithful — a persona-emulating Discord bot."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("faithful")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_errors.py -v
```
Expected: green.

- [ ] **Step 5: Commit**

```
git add faithful/__init__.py tests/test_errors.py
git commit -m "feat: expose package __version__"
```

---

## Task 6: CLI skeleton — `faithful/cli.py` with argparse + dispatcher

This task ships an empty-but-routable CLI. Verbs are stubs that do nothing; subsequent tasks fill them in.

**Files:**
- Create: `faithful/cli.py`
- Create: `tests/test_cli.py`
- Modify: `faithful/__main__.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:
```python
"""Tests for CLI argument parsing and dispatch."""
from pathlib import Path

import pytest

from faithful.cli import build_parser, main


def test_help_does_not_crash(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    out = capsys.readouterr().out
    assert "faithful" in out


def test_version_flag(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "faithful" in out


def test_subcommands_registered():
    parser = build_parser()
    # parse_args returns namespace with .verb set for each subcommand
    for verb in ("run", "doctor", "info"):
        args = parser.parse_args([verb])
        assert args.verb == verb


def test_no_args_means_setup(monkeypatch):
    parser = build_parser()
    args = parser.parse_args([])
    assert args.verb is None or args.verb == "setup"


def test_friendly_error_prints_to_stderr_and_returns_1(monkeypatch, capsys):
    from faithful.errors import FaithfulConfigError

    def boom(args, paths):
        raise FaithfulConfigError("nope")

    monkeypatch.setattr("faithful.cli.dispatch", boom)
    code = main(["info"])
    assert code == 1
    err = capsys.readouterr().err
    assert "nope" in err
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_cli.py -v
```
Expected: collection error — module missing.

- [ ] **Step 3: Implement `faithful/cli.py`**

```python
"""Command-line entry point for faithful.

Verbs:
- (no verb)   -> if no config exists, run wizard. If config exists, error.
- run         -> start the bot.
- doctor      -> connectivity diagnostics.
- info        -> print resolved paths and version.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .errors import FaithfulError
from .paths import ResolvedPaths, resolve_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="faithful",
        description="A Discord chatbot that emulates the tone of provided example messages.",
    )
    parser.add_argument(
        "--version", action="version", version=f"faithful {__version__}"
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="path to config.toml (default: ~/.faithful/config.toml)",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=None, dest="data_dir",
        help="path to data directory (default: ~/.faithful/data/)",
    )

    sub = parser.add_subparsers(dest="verb")

    run_p = sub.add_parser("run", help="start the bot")
    run_p.add_argument(
        "--version", action="version", version=f"faithful {__version__}"
    )

    doctor_p = sub.add_parser("doctor", help="diagnose configuration and connectivity")
    doctor_p.add_argument(
        "--version", action="version", version=f"faithful {__version__}"
    )

    info_p = sub.add_parser("info", help="print resolved paths and version")
    info_p.add_argument(
        "--version", action="version", version=f"faithful {__version__}"
    )

    # Wizard-only flags: only meaningful when invoked with no verb.
    parser.add_argument(
        "--quick", action="store_true",
        help="(setup only) skip the printed invite URL",
    )
    parser.add_argument(
        "--no-validate", action="store_true", dest="no_validate",
        help="(setup only) skip live API key validation",
    )
    return parser


def dispatch(args: argparse.Namespace, paths: ResolvedPaths) -> int:
    """Route a parsed Namespace to its verb handler. Returns process exit code."""
    if args.verb == "run":
        from .verbs import run as run_verb
        return run_verb(paths)
    if args.verb == "doctor":
        from .verbs import doctor as doctor_verb
        return doctor_verb(paths)
    if args.verb == "info":
        from .verbs import info as info_verb
        return info_verb(paths)
    # No verb: setup wizard if config absent, else error.
    from .verbs import setup as setup_verb
    return setup_verb(paths, quick=args.quick, no_validate=args.no_validate)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = resolve_paths(args.config, args.data_dir)
    try:
        return dispatch(args, paths)
    except FaithfulError as e:
        prefix = "\033[31merror:\033[0m" if sys.stderr.isatty() else "error:"
        print(f"{prefix} {e}", file=sys.stderr)
        return 1
```

Create a stub `faithful/verbs.py` that all verbs will share (so `cli.dispatch()` resolves at import time once we test with mocks):

```python
"""Verb implementations. Each verb is a small function returning an exit code.

Filled in across the next several tasks.
"""
from __future__ import annotations

from .errors import FaithfulError
from .paths import ResolvedPaths


def info(paths: ResolvedPaths) -> int:
    raise FaithfulError("info not implemented yet")


def run(paths: ResolvedPaths) -> int:
    raise FaithfulError("run not implemented yet")


def doctor(paths: ResolvedPaths) -> int:
    raise FaithfulError("doctor not implemented yet")


def setup(paths: ResolvedPaths, *, quick: bool = False, no_validate: bool = False) -> int:
    raise FaithfulError("setup not implemented yet")
```

Replace `faithful/__main__.py` with:
```python
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_cli.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add faithful/cli.py faithful/verbs.py faithful/__main__.py tests/test_cli.py
git commit -m "feat: argparse-based CLI skeleton with verb dispatch"
```

---

## Task 7: Implement `faithful info`

**Files:**
- Modify: `faithful/verbs.py`
- Create: `tests/test_verbs_info.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_verbs_info.py`:
```python
"""Tests for the `info` verb."""
import os

from faithful.paths import ResolvedPaths
from faithful.verbs import info


def test_info_prints_version_and_paths(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("FAITHFUL_HOME", raising=False)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)

    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )

    code = info(paths)
    out = capsys.readouterr().out

    assert code == 0
    assert "faithful" in out
    assert str(tmp_path / "config.toml") in out
    assert str(tmp_path / "data") in out


def test_info_reports_env_overrides(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_TOKEN", "x")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)

    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )

    code = info(paths)
    out = capsys.readouterr().out

    assert code == 0
    assert "FAITHFUL_HOME" in out
    assert "DISCORD_TOKEN" in out
    assert "API_KEY" not in out  # only set vars are reported
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_verbs_info.py -v
```
Expected: 2 fail with "info not implemented yet".

- [ ] **Step 3: Implement `info` in `faithful/verbs.py`**

Replace the `info` stub with:

```python
def info(paths: ResolvedPaths) -> int:
    import os

    from . import __version__

    print(f"faithful {__version__}")
    print(f"  home:        {paths.home}")
    print(f"  config:      {paths.config_path}")
    print(f"  data dir:    {paths.data_dir}")
    print(f"  config exists: {paths.config_path.is_file()}")

    env_vars = ("FAITHFUL_HOME", "DISCORD_TOKEN", "API_KEY", "ADMIN_USER_IDS", "ADMIN_USER_ID")
    set_vars = [v for v in env_vars if os.environ.get(v)]
    if set_vars:
        print("  env overrides: " + ", ".join(set_vars))

    if paths.config_path.is_file():
        try:
            from .config import Config
            cfg = Config.from_file(paths.config_path, data_dir=paths.data_dir)
            print(f"  active backend: {cfg.backend.active}")
            if cfg.backend.model:
                print(f"  model: {cfg.backend.model}")
        except Exception as e:  # noqa: BLE001 — info should never crash
            print(f"  (could not load config: {e})")

    return 0
```

(The `import os` at function top is intentional — keeps the module-level imports light.)

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_verbs_info.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```
git add faithful/verbs.py tests/test_verbs_info.py
git commit -m "feat: faithful info verb prints paths, version, env overrides"
```

---

## Task 8: Implement `faithful run`

**Files:**
- Modify: `faithful/verbs.py`
- Modify: `faithful/bot.py` (already takes a Config — no path computation; verify only)

- [ ] **Step 1: Write the failing test**

Create `tests/test_verbs_run.py`:
```python
"""Tests for the `run` verb."""
from unittest.mock import MagicMock, patch

import pytest

from faithful.errors import FaithfulConfigError
from faithful.paths import ResolvedPaths
from faithful.verbs import run


def test_run_errors_when_no_config(tmp_path):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "missing.toml",
        data_dir=tmp_path / "data",
    )
    with pytest.raises(FaithfulConfigError) as exc:
        run(paths)
    assert "No config" in str(exc.value)


@patch("faithful.bot.Faithful")
def test_run_starts_bot_when_config_exists(MockBot, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[discord]\ntoken = "tok"\nadmin_ids = [1]\n'
        '[backend]\napi_key = "k"\nmodel = "m"\n'
    )

    paths = ResolvedPaths(
        home=tmp_path,
        config_path=config_path,
        data_dir=tmp_path / "data",
    )

    instance = MagicMock()
    MockBot.return_value = instance

    code = run(paths)

    assert code == 0
    MockBot.assert_called_once()
    instance.run.assert_called_once_with("tok", log_handler=None)
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_verbs_run.py -v
```
Expected: 2 fail.

- [ ] **Step 3: Implement `run`**

Replace the `run` stub in `faithful/verbs.py`:

```python
def run(paths: ResolvedPaths) -> int:
    import logging

    from .bot import Faithful
    from .config import Config
    from .paths import ensure_home_exists

    ensure_home_exists(paths)
    cfg = Config.from_file(paths.config_path, data_dir=paths.data_dir)
    cfg.validate()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s",
    )

    bot = Faithful(cfg)
    bot.run(cfg.discord.token, log_handler=None)
    return 0
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_verbs_run.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```
git add faithful/verbs.py tests/test_verbs_run.py
git commit -m "feat: faithful run verb starts the bot from resolved paths"
```

---

## Task 9: Wizard scaffold — banner + token + admin IDs

This task installs the wizard module shell and the first three prompts. Subsequent tasks add backend selection, validation, TOML writing, and invite URL printing.

**Files:**
- Create: `faithful/wizard.py`
- Create: `tests/test_wizard.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wizard.py`:
```python
"""Tests for the interactive wizard."""
from io import StringIO

import pytest

from faithful.wizard import (
    WizardState,
    prompt_admin_ids,
    prompt_token,
)


def test_prompt_token_strips_whitespace(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "  abc.def.ghi  \n")
    token = prompt_token()
    assert token == "abc.def.ghi"


def test_prompt_token_rejects_empty(monkeypatch):
    answers = iter(["", "  ", "real-token"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(answers))
    token = prompt_token()
    assert token == "real-token"


def test_prompt_admin_ids_parses_csv(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "111, 222 ,333")
    ids = prompt_admin_ids()
    assert ids == [111, 222, 333]


def test_prompt_admin_ids_rejects_non_int(monkeypatch):
    answers = iter(["abc", "111,xyz", "111,222"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    ids = prompt_admin_ids()
    assert ids == [111, 222]


def test_wizard_state_holds_collected_values():
    state = WizardState()
    state.token = "t"
    state.admin_ids = [1]
    assert state.token == "t"
    assert state.admin_ids == [1]
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_wizard.py -v
```
Expected: import error.

- [ ] **Step 3: Implement `faithful/wizard.py`**

```python
"""Interactive first-run wizard for faithful.

Pure stdin/stdout. Tested by monkeypatching ``builtins.input`` and
``getpass.getpass``. Nothing is written to disk until the very end.
"""
from __future__ import annotations

import getpass
from dataclasses import dataclass, field

BANNER = """
faithful first-run setup

This will walk you through configuring the bot. Takes ~2 minutes.
Press Ctrl+C any time to abort. Nothing is written to disk until
the end.
"""


@dataclass
class WizardState:
    """All values collected during a wizard run."""

    token: str = ""
    admin_ids: list[int] = field(default_factory=list)
    backend: str = ""
    api_key: str = ""
    model: str = ""
    base_url: str = ""


def print_banner() -> None:
    print(BANNER)


def prompt_token() -> str:
    """Prompt for a Discord bot token. Re-prompts on empty input."""
    print(
        "Discord bot token "
        "(https://discord.com/developers/applications -> your app -> Bot -> Reset Token):"
    )
    while True:
        raw = getpass.getpass("token (hidden): ")
        cleaned = raw.strip()
        if cleaned:
            return cleaned
        print("Empty token — please paste your bot token.")


def prompt_admin_ids() -> list[int]:
    """Prompt for Discord user IDs (comma-separated). Re-prompts on parse failure."""
    print(
        "\nYour Discord user ID(s), comma-separated. "
        "Enable Developer Mode in Discord -> right-click your name -> Copy User ID:"
    )
    while True:
        raw = input("admin IDs: ").strip()
        if not raw:
            print("Need at least one admin ID.")
            continue
        try:
            ids = [int(part.strip()) for part in raw.split(",") if part.strip()]
        except ValueError:
            print("Each ID must be an integer (e.g. 123456789012345678).")
            continue
        if ids:
            return ids
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_wizard.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add faithful/wizard.py tests/test_wizard.py
git commit -m "feat: wizard scaffold with token and admin-ID prompts"
```

---

## Task 10: Wizard — backend menu + per-backend prompts

**Files:**
- Modify: `faithful/wizard.py`
- Modify: `tests/test_wizard.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_wizard.py`:
```python
from faithful.wizard import BACKEND_DEFAULTS, prompt_backend, prompt_credentials


def test_backend_defaults_cover_all_known_backends():
    assert set(BACKEND_DEFAULTS) == {"openai", "openai-compatible", "gemini", "anthropic"}


def test_prompt_backend_picks_choice(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "3")
    backend = prompt_backend()
    # menu order: 1=openai, 2=openai-compatible, 3=gemini, 4=anthropic
    assert backend == "gemini"


def test_prompt_backend_rejects_garbage(monkeypatch):
    answers = iter(["", "x", "9", "1"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    assert prompt_backend() == "openai"


def test_prompt_credentials_uses_default_model(monkeypatch):
    inputs = iter([""])           # empty model -> use default
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "sk-test")
    api_key, model, base_url = prompt_credentials("openai")
    assert api_key == "sk-test"
    assert model == BACKEND_DEFAULTS["openai"]["default_model"]
    assert base_url == ""


def test_prompt_credentials_openai_compatible_requires_base_url(monkeypatch):
    inputs = iter(["", "http://localhost:11434/v1", "llama3.2"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "")  # no key
    api_key, model, base_url = prompt_credentials("openai-compatible")
    assert api_key == ""
    assert model == "llama3.2"
    assert base_url == "http://localhost:11434/v1"
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_wizard.py -v
```
Expected: 5 new failures.

- [ ] **Step 3: Implement**

Append to `faithful/wizard.py`:
```python
BACKEND_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "label": "OpenAI (GPT models)",
        "key_url": "https://platform.openai.com/api-keys",
        "default_model": "gpt-4o-mini",
    },
    "openai-compatible": {
        "label": "Ollama / LM Studio / vLLM / any OpenAI-compatible server",
        "key_url": "",
        "default_model": "",
    },
    "gemini": {
        "label": "Google Gemini",
        "key_url": "https://aistudio.google.com/apikey",
        "default_model": "gemini-2.0-flash",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "key_url": "https://console.anthropic.com/settings/keys",
        "default_model": "claude-haiku-4-5",
    },
}

# Stable order matches the menu the user sees.
_BACKEND_ORDER = ["openai", "openai-compatible", "gemini", "anthropic"]


def prompt_backend() -> str:
    """Show the numbered backend menu and return the chosen key."""
    print("\nChoose a backend:")
    for i, name in enumerate(_BACKEND_ORDER, start=1):
        print(f"  {i}) {name:<20} — {BACKEND_DEFAULTS[name]['label']}")
    while True:
        raw = input("backend [1-4]: ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(_BACKEND_ORDER):
                return _BACKEND_ORDER[idx - 1]
        print("Pick a number 1-4.")


def prompt_credentials(backend: str) -> tuple[str, str, str]:
    """Prompt for api_key, model, base_url. Returns (api_key, model, base_url)."""
    info = BACKEND_DEFAULTS[backend]

    if backend == "openai-compatible":
        print(
            "\nbase_url for your OpenAI-compatible server "
            "(e.g. http://localhost:11434/v1 for Ollama):"
        )
        while True:
            base_url = input("base_url: ").strip()
            if base_url:
                break
            print("base_url is required for openai-compatible.")
        print(
            "API key (press Enter to skip if your local server doesn't need one):"
        )
        api_key = getpass.getpass("api_key (hidden): ").strip()
    else:
        base_url = ""
        if info["key_url"]:
            print(f"\nGet your API key at {info['key_url']}")
        api_key = getpass.getpass("api_key (hidden): ").strip()

    default_model = info["default_model"]
    if default_model:
        prompt = f"model name [{default_model}]: "
    else:
        prompt = "model name: "
    while True:
        raw = input(prompt).strip()
        if raw:
            return api_key, raw, base_url
        if default_model:
            return api_key, default_model, base_url
        print("Model name is required for this backend.")
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_wizard.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```
git add faithful/wizard.py tests/test_wizard.py
git commit -m "feat: wizard backend menu and credential prompts"
```

---

## Task 11: Wizard — live API key validation (skippable)

Implements `validate_credentials(backend, api_key, model, base_url)` returning `None` on success or a string error message on failure. Each backend uses the cheapest possible call. All wrapped in 5s timeout.

**Files:**
- Modify: `faithful/wizard.py`
- Modify: `tests/test_wizard.py`

- [ ] **Step 1: Append the failing tests**

```python
from unittest.mock import MagicMock, patch

from faithful.wizard import validate_credentials


def test_validate_openai_success():
    fake_client = MagicMock()
    fake_client.models.list.return_value = MagicMock()
    with patch("openai.OpenAI", return_value=fake_client):
        err = validate_credentials("openai", "sk-x", "gpt-4o-mini", "")
    assert err is None


def test_validate_openai_failure_returns_string():
    fake_client = MagicMock()
    fake_client.models.list.side_effect = RuntimeError("401 unauthorized")
    with patch("openai.OpenAI", return_value=fake_client):
        err = validate_credentials("openai", "sk-x", "gpt-4o-mini", "")
    assert err is not None
    assert "401" in err


def test_validate_anthropic_success():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = MagicMock()
    with patch("anthropic.Anthropic", return_value=fake_client):
        err = validate_credentials("anthropic", "sk-ant", "claude-haiku-4-5", "")
    assert err is None


def test_validate_openai_compatible_skipped_without_key():
    err = validate_credentials("openai-compatible", "", "llama3.2", "http://x/v1")
    assert err is None  # nothing to validate
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_wizard.py -v -k validate
```
Expected: 4 fail.

- [ ] **Step 3: Implement**

Append to `faithful/wizard.py`:
```python
def validate_credentials(
    backend: str,
    api_key: str,
    model: str,
    base_url: str,
) -> str | None:
    """Fire one cheap call to confirm credentials work. Returns error string or None."""
    try:
        if backend == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key, timeout=5)
            client.models.list()
            return None

        if backend == "openai-compatible":
            if not api_key:
                return None  # local server with no auth — nothing to test
            import openai
            client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=5)
            client.models.list()
            return None

        if backend == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=5)
            client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "."}],
            )
            return None

        if backend == "gemini":
            from google import genai
            client = genai.Client(api_key=api_key)
            list(client.models.list())
            return None

        return f"unknown backend: {backend}"
    except Exception as e:  # noqa: BLE001 — any error becomes a user-visible string
        return f"{type(e).__name__}: {e}"
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_wizard.py -v -k validate
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add faithful/wizard.py tests/test_wizard.py
git commit -m "feat: wizard live API key validation per backend"
```

---

## Task 12: Wizard — TOML writer + invite URL builder

Two related pure functions: `render_config_toml(state)` returns a string, `build_invite_url(token)` parses the application ID out of a Discord token and returns the OAuth URL.

**Files:**
- Modify: `faithful/wizard.py`
- Modify: `tests/test_wizard.py`

- [ ] **Step 1: Append the failing tests**

```python
import base64

from faithful.wizard import build_invite_url, render_config_toml


def test_render_toml_minimum_fields():
    state = WizardState(
        token="tok",
        admin_ids=[111, 222],
        backend="openai",
        api_key="sk-x",
        model="gpt-4o-mini",
        base_url="",
    )
    out = render_config_toml(state)
    assert '[discord]' in out
    assert 'token = "tok"' in out
    assert 'admin_ids = [111, 222]' in out
    assert '[backend]' in out
    assert 'active = "openai"' in out
    assert 'api_key = "sk-x"' in out
    assert 'model = "gpt-4o-mini"' in out
    assert "Generated by 'faithful'" in out


def test_render_toml_includes_base_url_when_present():
    state = WizardState(
        token="t", admin_ids=[1],
        backend="openai-compatible", api_key="",
        model="llama3.2", base_url="http://localhost:11434/v1",
    )
    out = render_config_toml(state)
    assert 'base_url = "http://localhost:11434/v1"' in out


def test_build_invite_url_extracts_app_id():
    # Discord tokens are base64url(app_id).timestamp.hmac
    app_id = "123456789012345678"
    encoded = base64.urlsafe_b64encode(app_id.encode()).decode().rstrip("=")
    token = f"{encoded}.AAAAAA.BBBBBB"

    url = build_invite_url(token)

    assert url is not None
    assert f"client_id={app_id}" in url
    assert "scope=bot+applications.commands" in url
    assert "permissions=" in url


def test_build_invite_url_returns_none_on_garbage():
    assert build_invite_url("not-a-valid-token") is None
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_wizard.py -v -k "render_toml or invite_url"
```
Expected: 4 fail.

- [ ] **Step 3: Implement**

Append to `faithful/wizard.py`:
```python
import base64
from datetime import date

# Permissions integer: View Channel | Send Messages | Read Message History |
# Add Reactions | Use External Emojis. Reverify against current Discord docs
# during implementation.
_INVITE_PERMISSIONS = 274877966400


def render_config_toml(state: WizardState) -> str:
    """Render the WizardState as a TOML config file."""
    today = date.today().isoformat()
    lines = [
        f"# Generated by 'faithful' on {today}.",
        "# Edit any field. Run 'faithful doctor' to test.",
        "",
        "[discord]",
        f'token = "{_escape(state.token)}"',
        f"admin_ids = [{', '.join(str(i) for i in state.admin_ids)}]",
        "",
        "[backend]",
        f'active = "{state.backend}"',
        f'api_key = "{_escape(state.api_key)}"',
        f'model = "{_escape(state.model)}"',
    ]
    if state.base_url:
        lines.append(f'base_url = "{_escape(state.base_url)}"')
    lines.append("")
    return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    """Escape backslashes and double-quotes for a basic TOML string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_invite_url(token: str) -> str | None:
    """Extract the application ID from a Discord token and return an invite URL.

    Returns None if the token doesn't parse.
    """
    parts = token.split(".")
    if len(parts) < 2:
        return None
    encoded = parts[0]
    try:
        # Pad base64url to a multiple of 4
        padded = encoded + "=" * (-len(encoded) % 4)
        app_id = base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception:  # noqa: BLE001
        return None
    if not app_id.isdigit():
        return None
    return (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={app_id}"
        f"&permissions={_INVITE_PERMISSIONS}"
        "&scope=bot+applications.commands"
    )
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_wizard.py -v
```
Expected: 14 passed (5 + 5 + 4).

- [ ] **Step 5: Commit**

```
git add faithful/wizard.py tests/test_wizard.py
git commit -m "feat: wizard TOML writer and Discord invite URL builder"
```

---

## Task 13: Wizard — top-level `run_wizard` orchestrator + setup verb wiring

Glues all the pieces together. Writes the file with mode 0600. Hooks `setup` verb in `verbs.py` to call this and to error if config already exists.

**Files:**
- Modify: `faithful/wizard.py`
- Modify: `faithful/verbs.py`
- Modify: `tests/test_wizard.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append failing tests for `run_wizard`**

```python
from pathlib import Path

from faithful.paths import ResolvedPaths
from faithful.wizard import run_wizard


def test_run_wizard_writes_config_with_0600_mode(tmp_path, monkeypatch):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )

    inputs = iter([
        "111,222",        # admin IDs
        "1",              # backend = openai
        "",               # model = default
    ])
    # Token first segment is base64url("123456789012345678"), so build_invite_url parses it.
    secrets = iter([
        "MTIzNDU2Nzg5MDEyMzQ1Njc4.AAAA.BBBB",  # token
        "sk-test",                              # api_key
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(secrets))
    monkeypatch.setattr(
        "faithful.wizard.validate_credentials",
        lambda *a, **kw: None,
    )

    code = run_wizard(paths, quick=True, no_validate=False)

    assert code == 0
    assert paths.config_path.is_file()
    contents = paths.config_path.read_text()
    assert 'token = "RXhhbXBsZUFwcElk.AAAA.BBBB"' in contents
    assert 'admin_ids = [111, 222]' in contents
    mode = paths.config_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_run_wizard_skips_invite_url_when_quick(tmp_path, monkeypatch, capsys):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )
    inputs = iter(["1", "1", ""])
    secrets = iter(["MTIzNDU2Nzg5MDEyMzQ1Njc4.AAAA.BBBB", "k"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(secrets))
    monkeypatch.setattr("faithful.wizard.validate_credentials", lambda *a, **kw: None)

    run_wizard(paths, quick=True, no_validate=False)

    out = capsys.readouterr().out
    assert "discord.com/api/oauth2" not in out


def test_run_wizard_prints_invite_url_when_not_quick(tmp_path, monkeypatch, capsys):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )
    inputs = iter(["1", "1", ""])
    secrets = iter(["MTIzNDU2Nzg5MDEyMzQ1Njc4.AAAA.BBBB", "k"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(secrets))
    monkeypatch.setattr("faithful.wizard.validate_credentials", lambda *a, **kw: None)

    run_wizard(paths, quick=False, no_validate=False)

    out = capsys.readouterr().out
    assert "discord.com/api/oauth2" in out
```

Append to `tests/test_cli.py`:
```python
from faithful.errors import FaithfulConfigError


def test_setup_verb_errors_when_config_exists(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text("# placeholder\n")
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path))

    code = main([])  # bare faithful

    assert code == 1  # FaithfulError caught by main


def test_setup_verb_runs_wizard_when_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path))

    called = {}

    def fake_setup(paths, *, quick, no_validate):
        called["paths"] = paths
        return 0

    monkeypatch.setattr("faithful.verbs.setup", fake_setup)

    code = main([])

    assert code == 0
    assert called["paths"].home == tmp_path
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_wizard.py tests/test_cli.py -v
```
Expected: 3 wizard fails + 2 cli fails (the `setup` verb still raises NotImplemented).

- [ ] **Step 3: Implement `run_wizard` in `faithful/wizard.py`**

Append:
```python
import os

from .paths import ResolvedPaths, ensure_home_exists


def run_wizard(paths: ResolvedPaths, *, quick: bool, no_validate: bool) -> int:
    """Run the full interactive setup. Returns 0 on success."""
    ensure_home_exists(paths)
    print_banner()

    state = WizardState()
    state.token = prompt_token()
    state.admin_ids = prompt_admin_ids()
    state.backend = prompt_backend()
    state.api_key, state.model, state.base_url = prompt_credentials(state.backend)

    if not no_validate:
        print("\nValidating credentials...")
        err = validate_credentials(
            state.backend, state.api_key, state.model, state.base_url
        )
        if err is None:
            print("  ✓ credentials look good")
        else:
            print(f"  ✗ {err}")
            choice = input("\n[r]etry, [s]kip validation, [q]uit? ").strip().lower()
            if choice.startswith("q"):
                print("\nAborted. No config written.")
                return 1
            if choice.startswith("r"):
                # Re-prompt credentials only.
                state.api_key, state.model, state.base_url = prompt_credentials(
                    state.backend
                )

    contents = render_config_toml(state)

    # Atomic write with mode 0600.
    paths.config_path.write_text(contents)
    os.chmod(paths.config_path, 0o600)

    print(f"\nWrote {paths.config_path}")

    if not quick:
        url = build_invite_url(state.token)
        if url is not None:
            print("\nAdd the bot to a server with this link:")
            print(f"  {url}")
        else:
            print(
                "\nCouldn't parse the application ID from your token. Visit "
                "https://discord.com/developers/applications to find it manually."
            )

    print("\nDone. Run 'faithful run' to start the bot.")
    return 0
```

- [ ] **Step 4: Wire the `setup` verb in `faithful/verbs.py`**

Replace the `setup` stub:
```python
def setup(paths: ResolvedPaths, *, quick: bool = False, no_validate: bool = False) -> int:
    from .errors import FaithfulConfigError
    from .wizard import run_wizard

    if paths.config_path.is_file():
        raise FaithfulConfigError(
            f"Already configured at {paths.config_path}. "
            "Run 'faithful run' to start the bot. "
            "(Delete the file and re-run 'faithful' to redo setup.)"
        )
    return run_wizard(paths, quick=quick, no_validate=no_validate)
```

- [ ] **Step 5: Run to confirm pass**

```
pytest tests/test_wizard.py tests/test_cli.py tests/test_verbs_info.py tests/test_verbs_run.py -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```
git add faithful/wizard.py faithful/verbs.py tests/test_wizard.py tests/test_cli.py
git commit -m "feat: wizard orchestrator + setup verb wiring"
```

---

## Task 14: Implement `faithful doctor`

**Files:**
- Create: `faithful/doctor.py`
- Modify: `faithful/verbs.py`
- Create: `tests/test_doctor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_doctor.py`:
```python
"""Tests for the doctor verb."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from faithful.config import Config, BackendConfig, BehaviorConfig, DiscordConfig
from faithful.doctor import check_discord_token, check_llm_provider, run_doctor


@pytest.fixture
def fake_config(tmp_path):
    cfg = Config(data_dir=tmp_path)
    cfg.discord = DiscordConfig(token="tok", admin_ids=[1])
    cfg.backend = BackendConfig(active="openai", api_key="sk-x", model="gpt-4o-mini")
    cfg.behavior = BehaviorConfig()
    return cfg


def test_check_discord_token_success():
    with patch("discord.Client") as MockClient:
        instance = MockClient.return_value
        instance.login = AsyncMock()
        instance.close = AsyncMock()
        err = check_discord_token("tok")
    assert err is None


def test_check_discord_token_invalid():
    import discord
    with patch("discord.Client") as MockClient:
        instance = MockClient.return_value
        instance.login = AsyncMock(side_effect=discord.LoginFailure("bad"))
        instance.close = AsyncMock()
        err = check_discord_token("tok")
    assert err is not None
    assert "bad" in err or "invalid" in err.lower()


def test_check_llm_provider_uses_wizard_validator(fake_config, monkeypatch):
    monkeypatch.setattr(
        "faithful.doctor.validate_credentials",
        lambda *a, **kw: None,
    )
    err = check_llm_provider(fake_config)
    assert err is None


def test_run_doctor_returns_zero_when_all_pass(fake_config, monkeypatch, capsys):
    monkeypatch.setattr("faithful.doctor.check_discord_token", lambda _: None)
    monkeypatch.setattr("faithful.doctor.check_llm_provider", lambda _: None)
    code = run_doctor(fake_config)
    out = capsys.readouterr().out
    assert code == 0
    assert "✓" in out


def test_run_doctor_returns_one_when_any_fails(fake_config, monkeypatch, capsys):
    monkeypatch.setattr("faithful.doctor.check_discord_token", lambda _: "bad token")
    monkeypatch.setattr("faithful.doctor.check_llm_provider", lambda _: None)
    code = run_doctor(fake_config)
    out = capsys.readouterr().out
    assert code == 1
    assert "✗" in out
    assert "bad token" in out
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_doctor.py -v
```
Expected: import error.

- [ ] **Step 3: Implement `faithful/doctor.py`**

```python
"""Diagnostic checks for ``faithful doctor``."""
from __future__ import annotations

import asyncio

from .config import Config
from .wizard import validate_credentials


def check_discord_token(token: str) -> str | None:
    """Try to log in to Discord with the token. Returns error string or None."""
    import discord

    async def _try():
        client = discord.Client(intents=discord.Intents.default())
        try:
            await asyncio.wait_for(client.login(token), timeout=10)
        except discord.LoginFailure as e:
            return f"invalid token: {e}"
        except asyncio.TimeoutError:
            return "connection timed out after 10s"
        except Exception as e:  # noqa: BLE001
            return f"{type(e).__name__}: {e}"
        finally:
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                pass
        return None

    return asyncio.run(_try())


def check_llm_provider(config: Config) -> str | None:
    """Reuse the wizard's per-backend validator."""
    return validate_credentials(
        config.backend.active,
        config.backend.api_key,
        config.backend.model,
        config.backend.base_url,
    )


def run_doctor(config: Config) -> int:
    """Run all checks and print a checklist. Returns exit code (0 = all pass)."""
    failed = 0

    print("Running diagnostics...\n")
    print(f"  ✓ config loaded ({config.backend.active})")
    if config.data_dir.is_dir():
        print(f"  ✓ data dir at {config.data_dir}")
    else:
        print(f"  ✗ data dir missing at {config.data_dir}")
        failed += 1

    err = check_discord_token(config.discord.token)
    if err is None:
        print("  ✓ Discord token valid")
    else:
        print(f"  ✗ Discord: {err}")
        failed += 1

    err = check_llm_provider(config)
    if err is None:
        print(f"  ✓ {config.backend.active}: {config.backend.model} OK")
    else:
        print(f"  ✗ {config.backend.active}: {err}")
        failed += 1

    if failed == 0:
        print("\nAll checks passed.")
        return 0
    print(f"\n{failed} check(s) failed.")
    return 1
```

- [ ] **Step 4: Wire the `doctor` verb in `faithful/verbs.py`**

Replace the `doctor` stub:
```python
def doctor(paths: ResolvedPaths) -> int:
    from .config import Config
    from .doctor import run_doctor

    cfg = Config.from_file(paths.config_path, data_dir=paths.data_dir)
    cfg.validate()
    return run_doctor(cfg)
```

- [ ] **Step 5: Run to confirm pass**

```
pytest tests/test_doctor.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```
git add faithful/doctor.py faithful/verbs.py tests/test_doctor.py
git commit -m "feat: faithful doctor verb with Discord and LLM provider checks"
```

---

## Task 15: Onboarding cog — `seen_guilds.json` + welcome DM with channel fallback

**Files:**
- Create: `faithful/cogs/onboarding.py`
- Create: `tests/test_onboarding.py`
- Modify: `faithful/bot.py` (load the new extension)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_onboarding.py`:
```python
"""Tests for the onboarding cog."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from faithful.cogs.onboarding import Onboarding


@pytest.fixture
def fake_bot(tmp_path):
    bot = MagicMock()
    bot.config = MagicMock()
    bot.config.data_dir = tmp_path
    bot.config.discord = MagicMock()
    bot.config.discord.admin_ids = [42]
    return bot


@pytest.mark.asyncio
async def test_dm_sent_on_first_join(fake_bot):
    cog = Onboarding(fake_bot)

    admin_user = MagicMock()
    admin_user.send = AsyncMock()
    fake_bot.get_user.return_value = admin_user

    guild = MagicMock(spec=discord.Guild)
    guild.id = 1234
    guild.name = "MyGuild"
    guild.text_channels = []

    await cog.on_guild_join(guild)

    admin_user.send.assert_called_once()
    args = admin_user.send.call_args[0]
    assert "MyGuild" in args[0]


@pytest.mark.asyncio
async def test_no_resend_after_restart(fake_bot, tmp_path):
    seen_path = tmp_path / "seen_guilds.json"
    seen_path.write_text(json.dumps([1234]))

    cog = Onboarding(fake_bot)

    admin_user = MagicMock()
    admin_user.send = AsyncMock()
    fake_bot.get_user.return_value = admin_user

    guild = MagicMock(spec=discord.Guild)
    guild.id = 1234
    guild.name = "MyGuild"
    guild.text_channels = []

    await cog.on_guild_join(guild)

    admin_user.send.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_channel_on_forbidden(fake_bot):
    cog = Onboarding(fake_bot)

    admin_user = MagicMock()
    admin_user.send = AsyncMock(
        side_effect=discord.Forbidden(MagicMock(), "DMs disabled")
    )
    fake_bot.get_user.return_value = admin_user

    chan = MagicMock(spec=discord.TextChannel)
    chan.send = AsyncMock()
    perms = MagicMock()
    perms.send_messages = True
    chan.permissions_for.return_value = perms

    guild = MagicMock(spec=discord.Guild)
    guild.id = 1234
    guild.name = "MyGuild"
    guild.text_channels = [chan]
    guild.me = MagicMock()

    await cog.on_guild_join(guild)

    chan.send.assert_called_once()
    msg = chan.send.call_args[0][0]
    assert "<@42>" in msg
    assert "MyGuild" in msg
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_onboarding.py -v
```
Expected: import error.

- [ ] **Step 3: Implement `faithful/cogs/onboarding.py`**

```python
"""Welcome admins on first guild join + provide a /help slash command."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from faithful.bot import Faithful

log = logging.getLogger("faithful.onboarding")

_WELCOME_TEXT = (
    "Hey — I just joined **{guild}**.\n\n"
    "To teach me how you talk, run `/upload` with a `.txt` file of example "
    "messages, or `/add_message` to add them one at a time. Run `/help` any "
    "time to see all commands."
)


class Onboarding(commands.Cog):
    """Welcome message + /help command."""

    def __init__(self, bot: "Faithful") -> None:
        self.bot = bot
        self._seen_path: Path = self.bot.config.data_dir / "seen_guilds.json"

    def _load_seen(self) -> set[int]:
        if not self._seen_path.is_file():
            return set()
        try:
            return set(json.loads(self._seen_path.read_text()))
        except (OSError, ValueError):
            log.warning("Could not read %s; treating as empty.", self._seen_path)
            return set()

    def _save_seen(self, seen: set[int]) -> None:
        self._seen_path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_path.write_text(json.dumps(sorted(seen)))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        seen = self._load_seen()
        if guild.id in seen:
            return

        text = _WELCOME_TEXT.format(guild=guild.name)
        any_delivered = False

        for admin_id in self.bot.config.discord.admin_ids:
            user = self.bot.get_user(admin_id)
            if user is None:
                log.warning("Admin user %d not in cache; skipping.", admin_id)
                continue
            try:
                await user.send(text)
                any_delivered = True
            except discord.Forbidden:
                # DMs disabled — fall back to the first writable text channel.
                if await self._post_in_first_writable_channel(guild, admin_id, text):
                    any_delivered = True
            except discord.DiscordException as e:
                log.warning("Failed to DM admin %d: %s", admin_id, e)

        if not any_delivered:
            log.warning("Could not reach any admin in guild %d", guild.id)

        seen.add(guild.id)
        self._save_seen(seen)

    async def _post_in_first_writable_channel(
        self, guild: discord.Guild, admin_id: int, text: str
    ) -> bool:
        for chan in guild.text_channels:
            perms = chan.permissions_for(guild.me)
            if perms.send_messages:
                try:
                    await chan.send(f"<@{admin_id}>\n{text}")
                    return True
                except discord.DiscordException as e:
                    log.warning("Failed to post in %s: %s", chan, e)
        return False

    @app_commands.command(name="help", description="Show available commands.")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="faithful — commands",
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name="Corpus (admin)",
            value=(
                "`/upload` — upload a .txt of example messages\n"
                "`/add_message` — add one message\n"
                "`/list_messages` — paginated list\n"
                "`/remove_message` — remove by index\n"
                "`/clear_messages` — wipe corpus\n"
                "`/download_messages` — export as .txt"
            ),
            inline=False,
        )
        embed.add_field(
            name="Memory (admin)",
            value="`/memory list/add/remove/clear`",
            inline=False,
        )
        embed.add_field(
            name="Diagnostics (admin)",
            value="`/status`, `/generate_test`",
            inline=False,
        )
        embed.set_footer(
            text="Config & data live at ~/.faithful/ on the host. "
                 "Run 'faithful info' on the host to see paths."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: "Faithful") -> None:
    await bot.add_cog(Onboarding(bot))
```

- [ ] **Step 4: Wire the cog in `faithful/bot.py`**

Add one line inside `setup_hook`, after the existing `load_extension` calls:
```python
        await self.load_extension("faithful.cogs.onboarding")
```

- [ ] **Step 5: Run to confirm pass**

```
pytest tests/test_onboarding.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```
git add faithful/cogs/onboarding.py faithful/bot.py tests/test_onboarding.py
git commit -m "feat: onboarding cog with welcome DM and /help"
```

---

## Task 16: Empty-state response in `cogs/chat.py`

Replace the silent `return` on empty corpus with a friendly reply when the user *directly* invokes the bot. Random-chance triggers continue to no-op silently when the corpus is empty.

**Files:**
- Modify: `faithful/cogs/chat.py` (lines ~134-159)
- Create: `tests/test_chat_empty_state.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_chat_empty_state.py`:
```python
"""Tests for the empty-corpus reply behaviour in chat.py."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from faithful.cogs.chat import EMPTY_STATE_TEXT, Chat


@pytest.mark.asyncio
async def test_replies_with_empty_state_when_pinged_and_corpus_empty():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.store.count = 0
    bot.config.behavior.reply_probability = 0.0
    bot.config.behavior.conversation_expiry = 300

    cog = Chat(bot)

    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.bot = False
    msg.guild = MagicMock()
    msg.reply = AsyncMock()
    bot.user.mentioned_in.return_value = True
    msg.reference = None
    msg.channel = MagicMock()

    await cog.on_message(msg)

    msg.reply.assert_awaited_once_with(EMPTY_STATE_TEXT)


@pytest.mark.asyncio
async def test_silent_when_random_trigger_and_corpus_empty():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.store.count = 0
    bot.config.behavior.reply_probability = 1.0  # would trigger if corpus existed
    bot.config.behavior.conversation_expiry = 300

    cog = Chat(bot)

    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.bot = False
    msg.guild = MagicMock()
    msg.reply = AsyncMock()
    bot.user.mentioned_in.return_value = False
    msg.reference = None
    msg.channel = MagicMock()
    # No history that contains the bot
    async def empty_history(limit):
        if False:
            yield
    msg.channel.history = MagicMock(return_value=empty_history(7))

    await cog.on_message(msg)

    msg.reply.assert_not_awaited()
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_chat_empty_state.py -v
```
Expected: 2 fail (one because `EMPTY_STATE_TEXT` doesn't exist, one because the silent path currently returns before any branch).

- [ ] **Step 3: Modify `faithful/cogs/chat.py`**

Add the constant near the top, after the existing `_REACTION_PROMPT`:
```python
EMPTY_STATE_TEXT = (
    "I don't have any example messages to learn from yet. "
    "An admin can use `/upload` or `/add_message` to teach me."
)
```

Replace the empty-corpus shortcut (currently lines 134-135):
```python
        if self.bot.store.count == 0:
            return
```
with:
```python
        if self.bot.store.count == 0:
            # Direct invocations get a friendly empty-state reply; random
            # triggers stay silent (don't burn API credits to say nothing).
            is_dm = message.guild is None
            is_mentioned = self._is_mentioned(message)
            if is_dm or is_mentioned:
                try:
                    await message.reply(EMPTY_STATE_TEXT)
                except discord.DiscordException:
                    log.exception("Failed to send empty-state reply")
            return
```

- [ ] **Step 4: Run to confirm pass**

```
pytest tests/test_chat_empty_state.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```
git add faithful/cogs/chat.py tests/test_chat_empty_state.py
git commit -m "feat: friendly empty-state reply on direct invocation"
```

---

## Task 17: `pyproject.toml` polish + version bump to 1.0.0

**Files:**
- Modify: `pyproject.toml`
- Modify: `config.example.toml` (header comment update — wizard now generates the real file)

- [ ] **Step 1: Replace `pyproject.toml` with the polished version**

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
dependencies = [
    "discord.py>=2.3",
    "tomli>=2.0; python_version < '3.11'",
    "duckduckgo-search>=7.0",
    "aiohttp>=3.9",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
openai = ["openai>=1.68"]
gemini = ["google-genai>=1.0"]
anthropic = ["anthropic>=0.40"]
all = [
    "openai>=1.68",
    "google-genai>=1.0",
    "anthropic>=0.40",
]
dev = [
    "openai>=1.68",
    "google-genai>=1.0",
    "anthropic>=0.40",
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[project.scripts]
faithful = "faithful.cli:main"

[project.urls]
Homepage = "https://github.com/a9lim/faithful"
Repository = "https://github.com/a9lim/faithful"
Issues = "https://github.com/a9lim/faithful/issues"

[tool.setuptools.packages.find]
include = ["faithful*"]
```

(`project.scripts` now points at `faithful.cli:main` rather than the old `faithful.__main__:main` — `main` lives in `cli.py` after Task 6.)

- [ ] **Step 2: Update `config.example.toml` header**

Replace the first three lines (the `# Faithful Discord Bot Configuration` header) with:
```toml
# Reference config for faithful.
#
# You typically don't need to write this by hand — run `faithful` with no
# config and the wizard will generate ~/.faithful/config.toml for you.
# This file documents every setting for power users who want to hand-edit.
```

- [ ] **Step 3: Verify the package still installs and tests pass**

```
pip install -e ".[dev]"
pytest tests/ -v
```
Expected: all tests green.

- [ ] **Step 4: Quick smoke test of the CLI**

```
faithful --version
```
Expected output: `faithful 1.0.0`.

```
faithful info
```
Expected: prints version + `~/.faithful/config.toml` (or whatever paths.py resolves).

- [ ] **Step 5: Commit**

```
git add pyproject.toml config.example.toml
git commit -m "chore: bump to 1.0.0; add PyPI classifiers, URLs, keywords"
```

---

## Task 18: Final integration smoke test + README touch-up

Not a TDD task — just an end-to-end manual sanity check before declaring done.

**Files:**
- Modify: `README.md` (Quick Start section; mention `faithful` (no args) instead of `cp config.example.toml config.toml`)

- [ ] **Step 1: Update the Quick Start section in `README.md`**

Replace the entire range from the line `## Quick Start` through the line `python -m faithful` (and its closing triple-backtick) with:

````markdown
## Quick Start

```bash
pip install faithful
faithful                  # run the interactive setup wizard
faithful run              # start the bot
```

The wizard writes `~/.faithful/config.toml`. Run `faithful doctor` any time to
check connectivity, or `faithful info` to see where things live.

Override paths with `--config <path>`, `--data-dir <path>`, or `FAITHFUL_HOME=/some/dir`.
````

(Keep the existing Prerequisites and feature sections above; keep the Commands table and everything below unchanged.)

- [ ] **Step 2: Run the full test suite one last time**

```
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 3: Build and check the wheel**

```
pip install build
python -m build
ls dist/
```
Expected: a `faithful-1.0.0-py3-none-any.whl` and `faithful-1.0.0.tar.gz`.

```
unzip -p dist/faithful-1.0.0-py3-none-any.whl '*/METADATA' | head -40
```
Expected: classifiers, project URLs, keywords all present.

- [ ] **Step 4: Commit**

```
git add README.md
git commit -m "docs: update Quick Start for the wizard-based first-run flow"
```

---

## Done.

The branch should now be ready for:
1. A code-review pass (use `superpowers:requesting-code-review`).
2. A `twine upload` to TestPyPI for a final smoke test.
3. A real PyPI upload once TestPyPI looks good.

Both of those are out of scope for this plan — they're release operations, not feature work.
