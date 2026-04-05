"""Tests for faithful.backends.base — Backend features (lock, token tracking, media type)."""

from __future__ import annotations

import asyncio

from faithful.backends.base import Attachment, Backend, _detect_media_type


# ── _detect_media_type ─────────────────────────────────


class TestDetectMediaType:
    def test_jpeg(self):
        assert _detect_media_type(b"\xff\xd8\xff\xe0" + b"\x00" * 20) == "image/jpeg"

    def test_gif(self):
        assert _detect_media_type(b"GIF89a" + b"\x00" * 20) == "image/gif"

    def test_gif87(self):
        assert _detect_media_type(b"GIF87a" + b"\x00" * 20) == "image/gif"

    def test_webp(self):
        data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
        assert _detect_media_type(data) == "image/webp"

    def test_png(self):
        assert _detect_media_type(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20) == "image/png"

    def test_unknown_defaults_png(self):
        assert _detect_media_type(b"\x00\x00\x00\x00") == "image/png"

    def test_empty_defaults_png(self):
        assert _detect_media_type(b"") == "image/png"

    def test_webp_too_short(self):
        # RIFF header but too short for WEBP check
        assert _detect_media_type(b"RIFF\x00\x00") == "image/png"


# ── Attachment.media_type ──────────────────────────────


class TestAttachmentMediaType:
    def test_media_type_detects_jpeg(self):
        att = Attachment(filename="image.png", content_type="image/png", data=b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        # content_type says PNG but magic bytes say JPEG
        assert att.media_type == "image/jpeg"

    def test_media_type_detects_gif(self):
        att = Attachment(filename="x.bin", content_type="application/octet-stream", data=b"GIF89a" + b"\x00" * 20)
        assert att.media_type == "image/gif"

    def test_b64_still_works(self):
        att = Attachment(filename="t.bin", content_type="image/png", data=b"hello")
        assert att.b64 == "aGVsbG8="


# ── Backend lock and token tracking ────────────────────


class TestBackendInit:
    def test_has_lock(self):
        """Backend instances should have an asyncio.Lock."""
        # We can't instantiate Backend directly (abstract), but we can check
        # that the __init__ signature sets up the lock via a minimal subclass.
        class Stub(Backend):
            async def _call_api(self, system_prompt, messages, attachments=None):
                return ""

        from faithful.config import Config

        cfg = Config()
        stub = Stub(cfg)
        assert isinstance(stub._lock, asyncio.Lock)

    def test_token_tracking_initial(self):
        class Stub(Backend):
            async def _call_api(self, system_prompt, messages, attachments=None):
                return ""

        from faithful.config import Config

        cfg = Config()
        stub = Stub(cfg)
        assert stub.total_input_tokens == 0
        assert stub.total_output_tokens == 0

    def test_track_usage(self):
        class Stub(Backend):
            async def _call_api(self, system_prompt, messages, attachments=None):
                return ""

        from faithful.config import Config

        cfg = Config()
        stub = Stub(cfg)
        stub._track_usage(100, 200)
        assert stub.total_input_tokens == 100
        assert stub.total_output_tokens == 200
        stub._track_usage(50, 50)
        assert stub.total_input_tokens == 150
        assert stub.total_output_tokens == 250
