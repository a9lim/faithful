"""Tests for CLI argument parsing and dispatch."""
from pathlib import Path

import pytest

from faithful.cli import build_parser, main


def test_help_does_not_crash(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    out = capsys.readouterr().out
    assert "faithful" in out


def test_version_flag(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "faithful" in out


def test_subcommands_registered():
    parser = build_parser()
    # parse_args returns namespace with .verb set for each subcommand
    for verb in ("run", "doctor", "info"):
        args = parser.parse_args([verb])
        assert args.verb == verb


def test_no_args_means_setup(monkeypatch):
    parser = build_parser()
    args = parser.parse_args([])
    assert args.verb is None or args.verb == "setup"


def test_friendly_error_prints_to_stderr_and_returns_1(monkeypatch, capsys):
    from faithful.errors import FaithfulConfigError

    def boom(args, paths):
        raise FaithfulConfigError("nope")

    monkeypatch.setattr("faithful.cli.dispatch", boom)
    code = main(["info"])
    assert code == 1
    err = capsys.readouterr().err
    assert "nope" in err
