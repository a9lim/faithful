"""Tests for the interactive wizard."""
from io import StringIO

import pytest

from faithful.wizard import (
    WizardState,
    prompt_admin_ids,
    prompt_token,
)


def test_prompt_token_strips_whitespace(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "  abc.def.ghi  \n")
    token = prompt_token()
    assert token == "abc.def.ghi"


def test_prompt_token_rejects_empty(monkeypatch):
    answers = iter(["", "  ", "real-token"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(answers))
    token = prompt_token()
    assert token == "real-token"


def test_prompt_admin_ids_parses_csv(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "111, 222 ,333")
    ids = prompt_admin_ids()
    assert ids == [111, 222, 333]


def test_prompt_admin_ids_rejects_non_int(monkeypatch):
    answers = iter(["abc", "111,xyz", "111,222"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    ids = prompt_admin_ids()
    assert ids == [111, 222]


def test_prompt_admin_ids_rejects_only_commas(monkeypatch, capsys):
    answers = iter([",,,", "111"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    ids = prompt_admin_ids()
    assert ids == [111]
    out = capsys.readouterr().out
    assert "Need at least one valid ID" in out


def test_wizard_state_holds_collected_values():
    state = WizardState()
    state.token = "t"
    state.admin_ids = [1]
    assert state.token == "t"
    assert state.admin_ids == [1]


def test_backend_defaults_cover_all_known_backends():
    from faithful.wizard import BACKEND_DEFAULTS

    assert set(BACKEND_DEFAULTS) == {"openai", "openai-compatible", "gemini", "anthropic"}


def test_prompt_backend_picks_choice(monkeypatch):
    from faithful.wizard import prompt_backend

    monkeypatch.setattr("builtins.input", lambda _prompt: "3")
    backend = prompt_backend()
    # menu order: 1=openai, 2=openai-compatible, 3=gemini, 4=anthropic
    assert backend == "gemini"


def test_prompt_backend_rejects_garbage(monkeypatch):
    from faithful.wizard import prompt_backend

    answers = iter(["", "x", "9", "1"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    assert prompt_backend() == "openai"


def test_prompt_credentials_uses_default_model(monkeypatch):
    from faithful.wizard import BACKEND_DEFAULTS, prompt_credentials

    inputs = iter([""])  # empty model -> use default
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "sk-test")
    api_key, model, base_url = prompt_credentials("openai")
    assert api_key == "sk-test"
    assert model == BACKEND_DEFAULTS["openai"]["default_model"]
    assert base_url == ""


def test_prompt_credentials_openai_compatible_requires_base_url(monkeypatch):
    from faithful.wizard import prompt_credentials

    inputs = iter(["", "http://localhost:11434/v1", "llama3.2"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "")  # no key
    api_key, model, base_url = prompt_credentials("openai-compatible")
    assert api_key == ""
    assert model == "llama3.2"
    assert base_url == "http://localhost:11434/v1"


def test_validate_openai_success():
    from unittest.mock import MagicMock, patch

    from faithful.wizard import validate_credentials

    fake_client = MagicMock()
    fake_client.models.list.return_value = MagicMock()
    with patch("openai.OpenAI", return_value=fake_client):
        err = validate_credentials("openai", "sk-x", "gpt-4o-mini", "")
    assert err is None


def test_validate_openai_failure_returns_string():
    from unittest.mock import MagicMock, patch

    from faithful.wizard import validate_credentials

    fake_client = MagicMock()
    fake_client.models.list.side_effect = RuntimeError("401 unauthorized")
    with patch("openai.OpenAI", return_value=fake_client):
        err = validate_credentials("openai", "sk-x", "gpt-4o-mini", "")
    assert err is not None
    assert "401" in err


def test_validate_anthropic_success():
    from unittest.mock import MagicMock, patch

    from faithful.wizard import validate_credentials

    fake_client = MagicMock()
    fake_client.messages.create.return_value = MagicMock()
    with patch("anthropic.Anthropic", return_value=fake_client):
        err = validate_credentials("anthropic", "sk-ant", "claude-haiku-4-5", "")
    assert err is None


def test_validate_openai_compatible_skipped_without_key():
    from faithful.wizard import validate_credentials

    err = validate_credentials("openai-compatible", "", "llama3.2", "http://x/v1")
    assert err is None  # nothing to validate


import base64

from faithful.wizard import build_invite_url, render_config_toml


def test_render_toml_minimum_fields():
    state = WizardState(
        token="tok",
        admin_ids=[111, 222],
        backend="openai",
        api_key="sk-x",
        model="gpt-4o-mini",
        base_url="",
    )
    out = render_config_toml(state)
    assert '[discord]' in out
    assert 'token = "tok"' in out
    assert 'admin_ids = [111, 222]' in out
    assert '[backend]' in out
    assert 'active = "openai"' in out
    assert 'api_key = "sk-x"' in out
    assert 'model = "gpt-4o-mini"' in out
    assert "Generated by 'faithful'" in out


def test_render_toml_includes_base_url_when_present():
    state = WizardState(
        token="t", admin_ids=[1],
        backend="openai-compatible", api_key="",
        model="llama3.2", base_url="http://localhost:11434/v1",
    )
    out = render_config_toml(state)
    assert 'base_url = "http://localhost:11434/v1"' in out


def test_build_invite_url_extracts_app_id():
    # Discord tokens are base64url(app_id).timestamp.hmac
    app_id = "123456789012345678"
    encoded = base64.urlsafe_b64encode(app_id.encode()).decode().rstrip("=")
    token = f"{encoded}.AAAAAA.BBBBBB"

    url = build_invite_url(token)

    assert url is not None
    assert f"client_id={app_id}" in url
    assert "scope=bot+applications.commands" in url
    assert "permissions=330816" in url


def test_build_invite_url_returns_none_on_garbage():
    assert build_invite_url("not-a-valid-token") is None


from pathlib import Path

from faithful.paths import ResolvedPaths
from faithful.wizard import run_wizard


def test_run_wizard_writes_config_with_0600_mode(tmp_path, monkeypatch):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )

    inputs = iter([
        "111,222",        # admin IDs
        "1",              # backend = openai
        "",               # model = default
    ])
    # Token first segment is base64url("123456789012345678"), so build_invite_url parses it.
    secrets = iter([
        "MTIzNDU2Nzg5MDEyMzQ1Njc4.AAAA.BBBB",  # token
        "sk-test",                              # api_key
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(secrets))
    monkeypatch.setattr(
        "faithful.wizard.validate_credentials",
        lambda *a, **kw: None,
    )

    code = run_wizard(paths, quick=True, no_validate=False)

    assert code == 0
    assert paths.config_path.is_file()
    contents = paths.config_path.read_text()
    assert 'token = "MTIzNDU2Nzg5MDEyMzQ1Njc4.AAAA.BBBB"' in contents
    assert 'admin_ids = [111, 222]' in contents
    mode = paths.config_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_run_wizard_skips_invite_url_when_quick(tmp_path, monkeypatch, capsys):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )
    inputs = iter(["1", "1", ""])
    secrets = iter(["MTIzNDU2Nzg5MDEyMzQ1Njc4.AAAA.BBBB", "k"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(secrets))
    monkeypatch.setattr("faithful.wizard.validate_credentials", lambda *a, **kw: None)

    run_wizard(paths, quick=True, no_validate=False)

    out = capsys.readouterr().out
    assert "discord.com/api/oauth2" not in out


def test_run_wizard_prints_invite_url_when_not_quick(tmp_path, monkeypatch, capsys):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )
    inputs = iter(["1", "1", ""])
    secrets = iter(["MTIzNDU2Nzg5MDEyMzQ1Njc4.AAAA.BBBB", "k"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(secrets))
    monkeypatch.setattr("faithful.wizard.validate_credentials", lambda *a, **kw: None)

    run_wizard(paths, quick=False, no_validate=False)

    out = capsys.readouterr().out
    assert "discord.com/api/oauth2" in out
