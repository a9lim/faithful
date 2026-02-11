"""Message store — CRUD for the example-message corpus."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faithy.config import Config

log = logging.getLogger("faithy.store")


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
        
        # Ensure directory exists
        self._dir.mkdir(parents=True, exist_ok=True)

        # Gather all .txt files
        files = sorted([
            p for p in self._dir.iterdir() 
            if p.is_file() and p.suffix == ".txt"
        ])

        for p in files:
            self._load_txt(p)

        log.info(f"Loaded {len(self._messages)} messages from {len(files)} files.")

    def _load_txt(self, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.strip():
                        self._messages.append(line.strip())
                        self._source_map.append((path, i))
        except Exception:
            log.warning(f"Failed to load text file: {path}")

    def add_messages(self, lines: list[str]) -> int:
        """Add messages to the default 'messages.txt' file."""
        target = self._dir / "messages.txt"
        
        cleaned = [ln.strip() for ln in lines if ln.strip()]
        if not cleaned:
            return 0

        # Append to file
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

        # Since it's always .txt now
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
            log.error(f"Failed to remove message from {path}")

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
        """Return a copy of all messages."""
        return list(self._messages)

    def get_all_text(self) -> str:
        """Return the full corpus as a single newline-delimited string."""
        return "\n".join(self._messages)

    @property
    def count(self) -> int:
        return len(self._messages)
