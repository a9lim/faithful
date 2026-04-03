"""Tests for faithful.config — nested dataclass config with merge and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from faithful.config import (
    Config,
    DiscordConfig,
    BackendConfig,
    BehaviorConfig,
    LLMConfig,
    SchedulerConfig,
    _merge_dataclass,
    _clamp,
    _parse_admin_ids,
    DEFAULT_SYSTEM_PROMPT,
)


# ── _clamp ──────────────────────────────────────────────

class TestClamp:
    def test_in_range(self):
        assert _clamp(0.5, 0, 1, "x", 0.5) == 0.5

    def test_out_of_range_returns_default(self):
        assert _clamp(5.0, 0, 1, "x", 0.5) == 0.5

    def test_boundary_values(self):
        assert _clamp(0.0, 0, 1, "x", 0.5) == 0.0
        assert _clamp(1.0, 0, 1, "x", 0.5) == 1.0


# ── _parse_admin_ids ────────────────────────────────────

class TestParseAdminIds:
    def test_env_comma_separated(self):
        assert _parse_admin_ids("1, 2, 3", None) == [1, 2, 3]

    def test_env_single(self):
        assert _parse_admin_ids("42", None) == [42]

    def test_toml_list(self):
        assert _parse_admin_ids(None, [10, 20]) == [10, 20]

    def test_toml_single_int(self):
        assert _parse_admin_ids(None, 99) == [99]

    def test_empty(self):
        assert _parse_admin_ids(None, 0) == []
        assert _parse_admin_ids(None, []) == []
        assert _parse_admin_ids("", None) == []


# ── _merge_dataclass ────────────────────────────────────

class TestMergeDataclass:
    def test_shallow_merge(self):
        cfg = LLMConfig()
        _merge_dataclass(cfg, {"max_tokens": 999, "temperature": 0.5})
        assert cfg.max_tokens == 999
        assert cfg.temperature == 0.5

    def test_nested_merge(self):
        cfg = Config()
        _merge_dataclass(cfg, {
            "backend": {"active": "anthropic", "model": "test-model"},
            "llm": {"max_tokens": 4096},
        })
        assert cfg.backend.active == "anthropic"
        assert cfg.backend.model == "test-model"
        assert cfg.llm.max_tokens == 4096
        # Untouched fields keep defaults
        assert cfg.backend.enable_thinking is True

    def test_unknown_keys_ignored(self):
        cfg = LLMConfig()
        _merge_dataclass(cfg, {"nonexistent_key": 42})
        # No error, no change
        assert cfg.max_tokens == 16000

    def test_deep_nested(self):
        cfg = Config()
        _merge_dataclass(cfg, {"behavior": {"persona_name": "test"}})
        assert cfg.behavior.persona_name == "test"


# ── Section dataclass validation ────────────────────────

class TestLLMConfig:
    def test_defaults(self):
        c = LLMConfig()
        assert c.max_tokens == 16000
        assert c.temperature == 1.0
        assert c.sample_size == 300

    def test_clamps_temperature(self):
        c = LLMConfig(temperature=5.0)
        assert c.temperature == 1.0  # default

    def test_min_max_tokens(self):
        c = LLMConfig(max_tokens=-10)
        assert c.max_tokens == 1

    def test_min_sample_size(self):
        c = LLMConfig(sample_size=0)
        assert c.sample_size == 1


class TestBehaviorConfig:
    def test_defaults(self):
        c = BehaviorConfig()
        assert c.system_prompt == DEFAULT_SYSTEM_PROMPT
        assert c.max_session_messages == 50

    def test_clamps_probabilities(self):
        c = BehaviorConfig(reply_probability=2.0, reaction_probability=-1.0)
        assert c.reply_probability == 0.02
        assert c.reaction_probability == 0.05

    def test_clamps_debounce(self):
        c = BehaviorConfig(debounce_delay=999)
        assert c.debounce_delay == 3.0

    def test_min_session_messages(self):
        c = BehaviorConfig(max_session_messages=0)
        assert c.max_session_messages == 1

    def test_custom_system_prompt_preserved(self):
        c = BehaviorConfig(system_prompt="custom {name}")
        assert c.system_prompt == "custom {name}"


# ── Config.from_file ────────────────────────────────────

class TestConfigFromFile:
    def test_load_from_toml(self, tmp_path: Path):
        toml = tmp_path / "config.toml"
        toml.write_text(textwrap.dedent("""\
            [discord]
            token = "test-token"
            admin_ids = [1, 2]

            [backend]
            active = "anthropic"
            api_key = "sk-test"
            model = "claude-test"

            [llm]
            max_tokens = 8000
            temperature = 0.7

            [behavior]
            persona_name = "tester"
            enable_web_search = true

            [scheduler]
            channels = [123]
            min_hours = 6
        """))

        cfg = Config.from_file(toml)
        assert cfg.discord.token == "test-token"
        assert cfg.discord.admin_ids == [1, 2]
        assert cfg.backend.active == "anthropic"
        assert cfg.backend.api_key == "sk-test"
        assert cfg.backend.model == "claude-test"
        assert cfg.llm.max_tokens == 8000
        assert cfg.llm.temperature == 0.7
        assert cfg.behavior.persona_name == "tester"
        assert cfg.behavior.enable_web_search is True
        assert cfg.scheduler.channels == [123]
        assert cfg.scheduler.min_hours == 6

    def test_missing_file_uses_defaults(self, tmp_path: Path):
        cfg = Config.from_file(tmp_path / "nonexistent.toml")
        assert cfg.backend.active == "openai-compatible"
        assert cfg.llm.max_tokens == 16000

    def test_validate_missing_token(self, tmp_path: Path):
        cfg = Config.from_file(tmp_path / "nonexistent.toml")
        with pytest.raises(ValueError, match="Discord token required"):
            cfg.validate()

    def test_validate_missing_admin_ids(self, tmp_path: Path):
        toml = tmp_path / "config.toml"
        toml.write_text('[discord]\ntoken = "tok"\n')
        cfg = Config.from_file(toml)
        with pytest.raises(ValueError, match="Admin IDs required"):
            cfg.validate()

    def test_revalidation_after_merge(self, tmp_path: Path):
        """Validation re-runs __post_init__ so out-of-range values get clamped."""
        toml = tmp_path / "config.toml"
        toml.write_text(textwrap.dedent("""\
            [discord]
            token = "tok"
            admin_ids = [1]

            [llm]
            temperature = 99.0
        """))
        cfg = Config.from_file(toml)
        assert cfg.llm.temperature == 1.0  # clamped back to default


class TestConfigEnvOverrides:
    def test_discord_token_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("DISCORD_TOKEN", "env-token")
        cfg = Config.from_file(tmp_path / "nonexistent.toml")
        assert cfg.discord.token == "env-token"

    def test_api_key_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("API_KEY", "env-key")
        cfg = Config.from_file(tmp_path / "nonexistent.toml")
        assert cfg.backend.api_key == "env-key"

    def test_admin_ids_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("ADMIN_USER_IDS", "10,20,30")
        cfg = Config.from_file(tmp_path / "nonexistent.toml")
        assert cfg.discord.admin_ids == [10, 20, 30]
