"""Verb implementations. Each verb is a small function returning an exit code.

Filled in across the next several tasks.
"""
from __future__ import annotations

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


def doctor(paths: ResolvedPaths) -> int:
    from .config import Config
    from .doctor import run_doctor

    cfg = Config.from_file(paths.config_path, data_dir=paths.data_dir)
    cfg.validate()
    return run_doctor(cfg)


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
