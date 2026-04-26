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
