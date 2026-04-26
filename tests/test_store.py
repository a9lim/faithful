"""Tests for faithful.store — message storage and sampling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from faithful.store import MessageStore


def _make_config(data_dir: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.data_dir = data_dir
    return cfg


class TestMessageStore:
    def test_empty_store(self, tmp_path: Path):
        store = MessageStore(_make_config(tmp_path))
        assert store.count == 0
        assert store.list_messages() == []

    def test_load_from_txt(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "msgs.txt").write_text("hello\nworld\n")
        store = MessageStore(_make_config(tmp_path))
        assert store.count == 2
        assert store.list_messages() == ["hello", "world"]

    def test_add_messages(self, tmp_path: Path):
        store = MessageStore(_make_config(tmp_path))
        added = store.add_messages(["one", "two", "  ", "three"])
        assert added == 3  # blank line stripped
        assert store.count == 3

    def test_remove_message(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "msgs.txt").write_text("a\nb\nc\n")
        store = MessageStore(_make_config(tmp_path))
        removed = store.remove_message(2)  # 1-based
        assert removed == "b"
        assert store.count == 2
        assert "b" not in store.list_messages()

    def test_remove_invalid_index(self, tmp_path: Path):
        store = MessageStore(_make_config(tmp_path))
        with pytest.raises(IndexError):
            store.remove_message(999)

    def test_clear_messages(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "msgs.txt").write_text("a\nb\n")
        store = MessageStore(_make_config(tmp_path))
        count = store.clear_messages()
        assert count == 2
        assert store.count == 0

    def test_get_all_text(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "msgs.txt").write_text("one\ntwo\n")
        store = MessageStore(_make_config(tmp_path))
        assert store.get_all_text() == "one\ntwo"

    def test_reload(self, tmp_path: Path):
        store = MessageStore(_make_config(tmp_path))
        assert store.count == 0
        (tmp_path / "persona").mkdir(exist_ok=True)
        (tmp_path / "persona" / "msgs.txt").write_text("added later\n")
        store.reload()
        assert store.count == 1

    def test_multiple_files(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "a.txt").write_text("from_a\n")
        (tmp_path / "persona" / "b.txt").write_text("from_b\n")
        store = MessageStore(_make_config(tmp_path))
        assert store.count == 2
        msgs = store.list_messages()
        assert "from_a" in msgs
        assert "from_b" in msgs

    def test_skip_empty_lines(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "msgs.txt").write_text("hello\n\n\nworld\n")
        store = MessageStore(_make_config(tmp_path))
        assert store.count == 2


class TestSampling:
    def test_sample_fewer_than_available(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "msgs.txt").write_text("\n".join(f"msg{i}" for i in range(20)) + "\n")
        store = MessageStore(_make_config(tmp_path))
        sample = store.get_sampled_messages(5)
        assert len(sample) == 5
        assert len(set(sample)) == 5  # no duplicates

    def test_sample_more_than_available(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "msgs.txt").write_text("one\ntwo\nthree\n")
        store = MessageStore(_make_config(tmp_path))
        sample = store.get_sampled_messages(100)
        assert len(sample) == 3

    def test_sample_empty(self, tmp_path: Path):
        store = MessageStore(_make_config(tmp_path))
        assert store.get_sampled_messages(5) == []

    def test_balanced_across_files(self, tmp_path: Path):
        (tmp_path / "persona").mkdir()
        (tmp_path / "persona" / "a.txt").write_text("\n".join(f"a{i}" for i in range(50)) + "\n")
        (tmp_path / "persona" / "b.txt").write_text("\n".join(f"b{i}" for i in range(50)) + "\n")
        store = MessageStore(_make_config(tmp_path))
        sample = store.get_sampled_messages(10)
        a_count = sum(1 for s in sample if s.startswith("a"))
        b_count = sum(1 for s in sample if s.startswith("b"))
        # Should be roughly balanced (at least 3 from each)
        assert a_count >= 3
        assert b_count >= 3


class TestPersonaSubdir:
    def test_store_writes_under_persona_subdir(self, tmp_path: Path):
        store = MessageStore(_make_config(tmp_path))
        store.add_messages(["hello"])
        assert (tmp_path / "persona" / "messages.txt").exists()
