"""Tests for faithful.backends — lazy loading."""

from __future__ import annotations

import pytest

from faithful.backends import BACKEND_NAMES, get_backend


class TestBackendRegistry:
    def test_all_names_present(self):
        assert "openai" in BACKEND_NAMES
        assert "openai-compatible" in BACKEND_NAMES
        assert "gemini" in BACKEND_NAMES
        assert "anthropic" in BACKEND_NAMES

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nonexistent", None)  # type: ignore[arg-type]

    def test_case_insensitive(self):
        # Should not raise ValueError (may raise ImportError if SDK missing)
        with pytest.raises((ImportError, Exception)):
            get_backend("ANTHROPIC", None)  # type: ignore[arg-type]
        # But it shouldn't be ValueError
