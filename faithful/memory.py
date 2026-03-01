"""Per-user and per-channel memory storage backed by JSON files."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("faithful.memory")

MAX_USER_FACTS = 20
MAX_CHANNEL_MEMORIES = 50


class MemoryStore:
    """Manages persistent memories stored as JSON files."""

    def __init__(self, data_dir: Path) -> None:
        self._users_dir = data_dir / "memories" / "users"
        self._channels_dir = data_dir / "memories" / "channels"
        self._users_dir.mkdir(parents=True, exist_ok=True)
        self._channels_dir.mkdir(parents=True, exist_ok=True)

    # ── User memories ────────────────────────────────────

    def _user_path(self, user_id: int) -> Path:
        return self._users_dir / f"{user_id}.json"

    def _load_user(self, user_id: int) -> dict:
        path = self._user_path(user_id)
        if not path.exists():
            return {"name": "", "facts": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.warning("Failed to load user memory for %d.", user_id)
            return {"name": "", "facts": []}

    def _save_user(self, user_id: int, data: dict) -> None:
        try:
            with open(self._user_path(user_id), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            log.warning("Failed to save user memory for %d.", user_id)

    def get_user_memories(self, user_id: int) -> tuple[str, list[str]]:
        """Return (display_name, facts) for a user."""
        data = self._load_user(user_id)
        return data.get("name", ""), data.get("facts", [])

    def add_user_memory(self, user_id: int, name: str, fact: str) -> None:
        """Add a fact about a user, updating their display name."""
        data = self._load_user(user_id)
        data["name"] = name
        facts = data.get("facts", [])
        facts.append(fact)
        if len(facts) > MAX_USER_FACTS:
            facts = facts[-MAX_USER_FACTS:]
        data["facts"] = facts
        self._save_user(user_id, data)

    def remove_user_memory(self, user_id: int, index: int) -> str:
        """Remove a fact by 0-based index. Returns the removed fact."""
        data = self._load_user(user_id)
        facts = data.get("facts", [])
        if index < 0 or index >= len(facts):
            raise IndexError(f"Index {index} out of range (have {len(facts)} facts).")
        removed = facts.pop(index)
        data["facts"] = facts
        self._save_user(user_id, data)
        return removed

    def clear_user_memories(self, user_id: int) -> int:
        """Clear all facts for a user. Returns count removed."""
        data = self._load_user(user_id)
        count = len(data.get("facts", []))
        data["facts"] = []
        self._save_user(user_id, data)
        return count

    # ── Channel memories ─────────────────────────────────

    def _channel_path(self, channel_id: int) -> Path:
        return self._channels_dir / f"{channel_id}.json"

    def _load_channel(self, channel_id: int) -> dict:
        path = self._channel_path(channel_id)
        if not path.exists():
            return {"memories": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.warning("Failed to load channel memory for %d.", channel_id)
            return {"memories": []}

    def _save_channel(self, channel_id: int, data: dict) -> None:
        try:
            with open(self._channel_path(channel_id), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            log.warning("Failed to save channel memory for %d.", channel_id)

    def get_channel_memories(self, channel_id: int) -> list[str]:
        """Return memories for a channel."""
        data = self._load_channel(channel_id)
        return data.get("memories", [])

    def add_channel_memory(self, channel_id: int, memory: str) -> None:
        """Add a memory to a channel."""
        data = self._load_channel(channel_id)
        memories = data.get("memories", [])
        memories.append(memory)
        if len(memories) > MAX_CHANNEL_MEMORIES:
            memories = memories[-MAX_CHANNEL_MEMORIES:]
        data["memories"] = memories
        self._save_channel(channel_id, data)

    def remove_channel_memory(self, channel_id: int, index: int) -> str:
        """Remove a memory by 0-based index. Returns the removed memory."""
        data = self._load_channel(channel_id)
        memories = data.get("memories", [])
        if index < 0 or index >= len(memories):
            raise IndexError(f"Index {index} out of range (have {len(memories)} memories).")
        removed = memories.pop(index)
        data["memories"] = memories
        self._save_channel(channel_id, data)
        return removed

    def clear_channel_memories(self, channel_id: int) -> int:
        """Clear all memories for a channel. Returns count removed."""
        data = self._load_channel(channel_id)
        count = len(data.get("memories", []))
        data["memories"] = []
        self._save_channel(channel_id, data)
        return count
