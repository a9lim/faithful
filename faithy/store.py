"""Message store — CRUD for the example-message corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faithy.config import Config


class MessageStore:
    """Persist example messages in a local JSON file."""

    def __init__(self, config: "Config") -> None:
        self.config = config
        self._dir: Path = config.data_dir
        self._messages: list[str] = []
        self._source_map: list[tuple[Path, int]] = []
        self.reload()

    def reload(self) -> None:
        """Scan data directory and load all messages."""
        self._messages.clear()
        self._source_map.clear()
        
        # Ensure directory exists
        self._dir.mkdir(parents=True, exist_ok=True)

        # Gather all .json and .txt files
        files = sorted([
            p for p in self._dir.iterdir() 
            if p.is_file() and p.suffix in {".json", ".txt"}
        ])

        for p in files:
            if p.suffix == ".json":
                self._load_json(p)
            else:
                self._load_txt(p)

    def _load_json(self, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for i, item in enumerate(data):
                        if isinstance(item, str) and item.strip():
                            self._messages.append(item.strip())
                            self._source_map.append((path, i))
        except Exception:
            pass

    def _load_txt(self, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.strip():
                        self._messages.append(line.strip())
                        self._source_map.append((path, i))
        except Exception:
            pass

    def add_messages(self, lines: list[str]) -> int:
        """Add messages to the default 'messages.json' file."""
        target = self._dir / "messages.json"
        
        # Load existing or create new
        existing = []
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except:
                pass
        
        cleaned = [ln.strip() for ln in lines if ln.strip()]
        existing.extend(cleaned)
        
        with open(target, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
            
        self.reload()
        return len(cleaned)

    def remove_message(self, index: int) -> str:
        """Remove a message by 1-based index (global) from its source file."""
        real_idx = index - 1
        if not (0 <= real_idx < len(self._messages)):
            raise IndexError("Invalid message index")
            
        path, file_idx = self._source_map[real_idx]
        removed_text = self._messages[real_idx]

        if path.suffix == ".json":
            self._remove_from_json(path, file_idx)
        else:
            self._remove_from_txt(path, file_idx)
            
        self.reload()
        return removed_text

    def _remove_from_json(self, path: Path, index: int) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if 0 <= index < len(data):
            data.pop(index)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _remove_from_txt(self, path: Path, index: int) -> None:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if 0 <= index < len(lines):
            lines.pop(index)
            
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def clear_messages(self) -> int:
        """Clear the default messages.json. Leave other files alone? 
        Or clear ALL?
        
        For safety, let's just clear messages.json, or maybe error if multiple files exist?
        The user request was 'upload multiple files'.
        Let's interpret clear_messages as: Delete messages.json content. 
        OR: Delete all message files?
        
        Ideally, clear_messages should clear 'everything loaded'.
        """
        count = len(self._messages)
        
        # Strategy: Delete all .json/.txt files in data_dir
        # except maybe we want to keep them but empty them?
        # Simpler: Delete the files.
        files = sorted([
            p for p in self._dir.iterdir() 
            if p.is_file() and p.suffix in {".json", ".txt"}
        ])
        
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
