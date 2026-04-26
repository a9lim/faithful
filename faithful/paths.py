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
