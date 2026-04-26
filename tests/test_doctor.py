"""Tests for the doctor verb."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from faithful.config import Config, BackendConfig, BehaviorConfig, DiscordConfig
from faithful.doctor import check_discord_token, check_llm_provider, run_doctor


@pytest.fixture
def fake_config(tmp_path):
    cfg = Config(data_dir=tmp_path)
    cfg.discord = DiscordConfig(token="tok", admin_ids=[1])
    cfg.backend = BackendConfig(active="openai", api_key="sk-x", model="gpt-4o-mini")
    cfg.behavior = BehaviorConfig()
    return cfg


def test_check_discord_token_success():
    with patch("discord.Client") as MockClient:
        instance = MockClient.return_value
        instance.login = AsyncMock()
        instance.close = AsyncMock()
        err = check_discord_token("tok")
    assert err is None


def test_check_discord_token_invalid():
    import discord
    with patch("discord.Client") as MockClient:
        instance = MockClient.return_value
        instance.login = AsyncMock(side_effect=discord.LoginFailure("bad"))
        instance.close = AsyncMock()
        err = check_discord_token("tok")
    assert err is not None
    assert "bad" in err or "invalid" in err.lower()


def test_check_llm_provider_uses_wizard_validator(fake_config, monkeypatch):
    monkeypatch.setattr(
        "faithful.doctor.validate_credentials",
        lambda *a, **kw: None,
    )
    err = check_llm_provider(fake_config)
    assert err is None


def test_run_doctor_returns_zero_when_all_pass(fake_config, monkeypatch, capsys):
    monkeypatch.setattr("faithful.doctor.check_discord_token", lambda _: None)
    monkeypatch.setattr("faithful.doctor.check_llm_provider", lambda _: None)
    code = run_doctor(fake_config)
    out = capsys.readouterr().out
    assert code == 0
    assert "✓" in out


def test_run_doctor_returns_one_when_any_fails(fake_config, monkeypatch, capsys):
    monkeypatch.setattr("faithful.doctor.check_discord_token", lambda _: "bad token")
    monkeypatch.setattr("faithful.doctor.check_llm_provider", lambda _: None)
    code = run_doctor(fake_config)
    out = capsys.readouterr().out
    assert code == 1
    assert "✗" in out
    assert "bad token" in out
