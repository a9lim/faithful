"""Tests for faithful.tools — MemoryExecutor file CRUD."""

from __future__ import annotations

from pathlib import Path

import pytest

from faithful.tools import MemoryExecutor


@pytest.fixture
def mem(tmp_path: Path) -> MemoryExecutor:
    return MemoryExecutor(tmp_path)


class TestMemoryExecutorCreate:
    def test_create_file(self, mem: MemoryExecutor):
        result = mem.execute({"command": "create", "path": "/memories/test.txt", "file_text": "hello"})
        assert "created successfully" in result

    def test_create_already_exists(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/test.txt", "file_text": "hello"})
        result = mem.execute({"command": "create", "path": "/memories/test.txt", "file_text": "again"})
        assert "already exists" in result

    def test_create_nested_dirs(self, mem: MemoryExecutor):
        result = mem.execute({"command": "create", "path": "/memories/a/b/c.txt", "file_text": "deep"})
        assert "created successfully" in result


class TestMemoryExecutorView:
    def test_view_file(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/notes.txt", "file_text": "line1\nline2\nline3"})
        result = mem.execute({"command": "view", "path": "/memories/notes.txt"})
        assert "line1" in result
        assert "line2" in result

    def test_view_with_range(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/notes.txt", "file_text": "a\nb\nc\nd\ne"})
        result = mem.execute({"command": "view", "path": "/memories/notes.txt", "view_range": [2, 3]})
        assert "b" in result
        assert "c" in result

    def test_view_directory(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/file.txt", "file_text": "content"})
        result = mem.execute({"command": "view", "path": "/memories"})
        assert "file.txt" in result

    def test_view_nonexistent(self, mem: MemoryExecutor):
        result = mem.execute({"command": "view", "path": "/memories/nope.txt"})
        assert "does not exist" in result


class TestMemoryExecutorStrReplace:
    def test_replace(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/f.txt", "file_text": "hello world"})
        result = mem.execute({
            "command": "str_replace", "path": "/memories/f.txt",
            "old_str": "world", "new_str": "earth",
        })
        assert "edited" in result

    def test_replace_not_found(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/f.txt", "file_text": "hello"})
        result = mem.execute({
            "command": "str_replace", "path": "/memories/f.txt",
            "old_str": "xyz", "new_str": "abc",
        })
        assert "did not appear" in result

    def test_replace_multiple_occurrences_rejected(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/f.txt", "file_text": "aa\naa\n"})
        result = mem.execute({
            "command": "str_replace", "path": "/memories/f.txt",
            "old_str": "aa", "new_str": "bb",
        })
        assert "Multiple occurrences" in result


class TestMemoryExecutorInsert:
    def test_insert_at_line(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/f.txt", "file_text": "a\nb"})
        result = mem.execute({
            "command": "insert", "path": "/memories/f.txt",
            "insert_line": 1, "insert_text": "inserted",
        })
        assert "edited" in result.lower()

    def test_insert_invalid_line(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/f.txt", "file_text": "a"})
        result = mem.execute({
            "command": "insert", "path": "/memories/f.txt",
            "insert_line": 999, "insert_text": "x",
        })
        assert "Invalid" in result


class TestMemoryExecutorDelete:
    def test_delete_file(self, mem: MemoryExecutor, tmp_path: Path):
        mem.execute({"command": "create", "path": "/memories/del.txt", "file_text": "bye"})
        result = mem.execute({"command": "delete", "path": "/memories/del.txt"})
        assert "deleted" in result.lower()

    def test_delete_nonexistent(self, mem: MemoryExecutor):
        result = mem.execute({"command": "delete", "path": "/memories/nope.txt"})
        assert "does not exist" in result


class TestMemoryExecutorRename:
    def test_rename(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/old.txt", "file_text": "data"})
        result = mem.execute({
            "command": "rename", "old_path": "/memories/old.txt",
            "new_path": "/memories/new.txt",
        })
        assert "renamed" in result.lower()

    def test_rename_destination_exists(self, mem: MemoryExecutor):
        mem.execute({"command": "create", "path": "/memories/a.txt", "file_text": "a"})
        mem.execute({"command": "create", "path": "/memories/b.txt", "file_text": "b"})
        result = mem.execute({
            "command": "rename", "old_path": "/memories/a.txt",
            "new_path": "/memories/b.txt",
        })
        assert "already exists" in result


class TestMemoryExecutorSecurity:
    def test_path_traversal_blocked(self, mem: MemoryExecutor):
        result = mem.execute({"command": "view", "path": "/memories/../../etc/passwd"})
        assert "traversal" in result.lower() or "escapes" in result.lower()

    def test_unknown_command(self, mem: MemoryExecutor):
        result = mem.execute({"command": "drop_table"})
        assert "Unknown command" in result
