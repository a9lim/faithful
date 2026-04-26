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
