from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faithful.config import Config

log = logging.getLogger("faithful.store")


class MessageStore:
    """Persist example messages in local text files."""

    def __init__(self, config: "Config") -> None:
        self.config = config
        self._dir: Path = config.data_dir
        self._messages: list[str] = []
        self._source_map: list[tuple[Path, int]] = []
        self.reload()

    def reload(self) -> None:
        """Scan data directory and load all .txt messages."""
        self._messages.clear()
        self._source_map.clear()

        self._dir.mkdir(parents=True, exist_ok=True)

        files = sorted([
            p for p in self._dir.iterdir()
            if p.is_file() and p.suffix == ".txt"
        ])

        for p in files:
            self._load_txt(p)

        log.info("Loaded %d messages from %d files.", len(self._messages), len(files))

    def _load_txt(self, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.strip():
                        self._messages.append(line.strip())
                        self._source_map.append((path, i))
        except Exception:
            log.exception("Failed to load text file: %s", path)

    def add_messages(self, lines: list[str]) -> int:
        """Add messages to the default 'messages.txt' file."""
        target = self._dir / "messages.txt"

        cleaned = [ln.strip() for ln in lines if ln.strip()]
        if not cleaned:
            return 0

        with open(target, "a", encoding="utf-8") as f:
            for line in cleaned:
                f.write(f"{line}\n")

        self.reload()
        return len(cleaned)

    def remove_message(self, index: int) -> str:
        """Remove a message by 1-based index (global) from its source file."""
        real_idx = index - 1
        if not (0 <= real_idx < len(self._messages)):
            raise IndexError("Invalid message index")

        path, file_idx = self._source_map[real_idx]
        removed_text = self._messages[real_idx]

        self._remove_from_txt(path, file_idx)
        self.reload()
        return removed_text

    def _remove_from_txt(self, path: Path, index: int) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if 0 <= index < len(lines):
                lines.pop(index)

            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            log.error("Failed to remove message from %s", path)

    def clear_messages(self) -> int:
        """Delete all .txt message files in the data directory."""
        count = len(self._messages)

        files = [
            p for p in self._dir.iterdir()
            if p.is_file() and p.suffix == ".txt"
        ]

        for p in files:
            p.unlink()

        self.reload()
        return count

    def list_messages(self) -> list[str]:
        return list(self._messages)

    def get_all_text(self) -> str:
        return "\n".join(self._messages)

    @property
    def count(self) -> int:
        return len(self._messages)

    def get_sampled_messages(self, count: int) -> list[str]:
        """Get a balanced sample of messages from all source files.

        Uses index tracking to avoid duplicates when filling remaining slots.
        """
        if not self._messages:
            return []

        if count >= len(self._messages):
            shuffled = list(self._messages)
            random.shuffle(shuffled)
            return shuffled

        # Group indices by source file
        by_file: dict[Path, list[int]] = {}
        for idx, (path, _) in enumerate(self._source_map):
            by_file.setdefault(path, []).append(idx)

        files = list(by_file.keys())
        if not files:
            return []

        per_file = max(1, count // len(files))

        selected: set[int] = set()
        for path in files:
            indices = by_file[path]
            k = min(len(indices), per_file)
            selected.update(random.sample(indices, k))

        # Fill remaining slots from unselected indices
        remaining_slots = count - len(selected)
        if remaining_slots > 0:
            unselected = [i for i in range(len(self._messages)) if i not in selected]
            if unselected:
                fill = min(len(unselected), remaining_slots)
                selected.update(random.sample(unselected, fill))

        result = [self._messages[i] for i in selected]
        random.shuffle(result)
        return result[:count]
