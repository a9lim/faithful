"""Tests for faithful.chunker — message splitting and reaction extraction."""

from __future__ import annotations

from faithful.chunker import _chunk_text, extract_reactions


class TestChunkText:
    def test_short_text_unchanged(self):
        assert _chunk_text("hello") == ["hello"]

    def test_empty_text(self):
        assert _chunk_text("") == [""]

    def test_exact_limit(self):
        text = "a" * 2000
        assert _chunk_text(text) == [text]

    def test_splits_long_text(self):
        text = "Hello world. " * 200  # well over 2000 chars
        chunks = _chunk_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 2000

    def test_prefers_sentence_boundary(self):
        # Build text where a sentence ends before the limit
        sentence = "This is a sentence. "
        text = sentence * 120  # ~2400 chars
        chunks = _chunk_text(text)
        assert len(chunks) >= 2
        # First chunk should end at a sentence boundary
        assert chunks[0].rstrip().endswith(".")

    def test_falls_back_to_space(self):
        # One very long "sentence" with no periods
        text = ("word " * 500).strip()
        chunks = _chunk_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 2000

    def test_hard_cut_no_spaces(self):
        text = "x" * 3000
        chunks = _chunk_text(text)
        assert len(chunks) == 2
        assert len(chunks[0]) == 2000
        assert len(chunks[1]) == 1000


class TestExtractReactions:
    def test_single_reaction(self):
        text, reactions = extract_reactions("Hello! [react: 👍]")
        assert text == "Hello!"
        assert reactions == ["👍"]

    def test_multiple_reactions(self):
        text, reactions = extract_reactions("Hi [react: 😊] bye [react: 👋]")
        assert text == "Hi  bye"
        assert reactions == ["😊", "👋"]

    def test_no_reactions(self):
        text, reactions = extract_reactions("Just a normal message")
        assert text == "Just a normal message"
        assert reactions == []

    def test_custom_emoji(self):
        text, reactions = extract_reactions("Nice [react: :custom_emoji:]")
        assert text == "Nice"
        assert reactions == [":custom_emoji:"]

    def test_whitespace_in_marker(self):
        text, reactions = extract_reactions("[react:   fire  ]")
        assert reactions == ["fire"]

    def test_empty_reaction_filtered(self):
        text, reactions = extract_reactions("[react:   ]")
        assert reactions == []
