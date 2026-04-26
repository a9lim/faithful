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
