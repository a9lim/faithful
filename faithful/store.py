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

    def get_sampled_messages(self, count: int) -> list[str]:
        """Get a balanced sample of messages from all source files.

        This ensures that even if one file has 10,000 messages and another has 50,
        we get a mix of both in the context, rather than the large file dominating.
        """
        if not self._messages:
            return []

        # If we want more than we have, just return everything shuffled
        if count >= len(self._messages):
            shuffled = list(self._messages)
            random.shuffle(shuffled)
            return shuffled

        # Group messages by source file path
        by_file: dict[Path, list[str]] = {}
        for msg, (path, _) in zip(self._messages, self._source_map):
            if path not in by_file:
                by_file[path] = []
            by_file[path].append(msg)

        files = list(by_file.keys())
        if not files:
            return []

        # Calculate how many to take from each file
        per_file = max(1, count // len(files))
        
        sampled_messages = []
        for path in files:
            msgs = by_file[path]
            # Take a random sample from this file's messages
            # Use min() in case a file has fewer messages than per_file
            k = min(len(msgs), per_file)
            sampled_messages.extend(random.sample(msgs, k))

        # If we still have room (due to rounding or small files), fill up randomly from remaining
        remaining_slots = count - len(sampled_messages)
        if remaining_slots > 0:
            # Create a pool of messages not yet selected (this is expensive to compute exactly,
            # so we'll just sample from all messages and deduplicate if strictness matters,
            # but for this use case, duplicates are rare/okay or we can just sample from all)
            # A cheaper way: just sample randomly from the full list to fill the gap.
            # Collisions are possible but low impact for chat context.
            sampled_messages.extend(random.sample(self._messages, remaining_slots))

        # Shuffle the final mix so the blocks aren't contiguous by file
        random.shuffle(sampled_messages)
        
        # Trim to exact count if we overshot (unlikely with this logic but good safety)
        return sampled_messages[:count]
