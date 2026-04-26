"""Verb implementations. Each verb is a small function returning an exit code.

Filled in across the next several tasks.
"""
from __future__ import annotations

from .errors import FaithfulError
from .paths import ResolvedPaths


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


def run(paths: ResolvedPaths) -> int:
    raise FaithfulError("run not implemented yet")


def doctor(paths: ResolvedPaths) -> int:
    raise FaithfulError("doctor not implemented yet")


def setup(paths: ResolvedPaths, *, quick: bool = False, no_validate: bool = False) -> int:
    raise FaithfulError("setup not implemented yet")
