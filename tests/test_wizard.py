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
