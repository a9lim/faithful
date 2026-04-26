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
