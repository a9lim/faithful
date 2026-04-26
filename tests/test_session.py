"""Tests for faithful.backends.base — SessionHistory."""

from __future__ import annotations

import time

from faithful.backends.base import SessionHistory


class TestSessionHistory:
    def test_append_and_messages(self):
        s = SessionHistory(channel_id=1, max_messages=10, expiry=300)
        s.append({"role": "user", "content": "hi"})
        s.append({"role": "assistant", "content": "hello"})
        assert len(s.messages) == 2
        assert s.messages[0]["content"] == "hi"

    def test_seed_replaces_messages(self):
        s = SessionHistory(channel_id=1, max_messages=10, expiry=300)
        s.append({"role": "user", "content": "old"})
        s.seed([{"role": "user", "content": "new"}])
        assert len(s.messages) == 1
        assert s.messages[0]["content"] == "new"

    def test_trim(self):
        s = SessionHistory(channel_id=1, max_messages=3, expiry=300)
        for i in range(5):
            s.append({"role": "user", "content": str(i)})
        s.trim()
        assert len(s.messages) == 3
        # Should keep the last 3
        assert s.messages[0]["content"] == "2"
        assert s.messages[2]["content"] == "4"

    def test_trim_no_op_when_under_limit(self):
        s = SessionHistory(channel_id=1, max_messages=10, expiry=300)
        s.append({"role": "user", "content": "only one"})
        s.trim()
        assert len(s.messages) == 1

    def test_expired(self):
        s = SessionHistory(channel_id=1, max_messages=10, expiry=0.01)
        assert not s.expired
        time.sleep(0.02)
        assert s.expired

    def test_touch_resets_expiry(self):
        s = SessionHistory(channel_id=1, max_messages=10, expiry=0.05)
        time.sleep(0.03)
        s.touch()
        assert not s.expired

    def test_seed_makes_copies(self):
        """Seed should copy dicts, not reference originals."""
        original = [{"role": "user", "content": "hi"}]
        s = SessionHistory(channel_id=1, max_messages=10, expiry=300)
        s.seed(original)
        s.messages[0]["content"] = "modified"
        assert original[0]["content"] == "hi"
