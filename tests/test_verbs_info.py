"""Tests for the `info` verb."""

from faithful.paths import ResolvedPaths
from faithful.verbs import info


def test_info_prints_version_and_paths(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("FAITHFUL_HOME", raising=False)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)

    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )

    code = info(paths)
    out = capsys.readouterr().out

    assert code == 0
    assert "faithful" in out
    assert str(tmp_path / "config.toml") in out
    assert str(tmp_path / "data") in out


def test_info_reports_env_overrides(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_TOKEN", "x")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)

    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "data",
    )

    code = info(paths)
    out = capsys.readouterr().out

    assert code == 0
    assert "FAITHFUL_HOME" in out
    assert "DISCORD_TOKEN" in out
    assert "API_KEY" not in out  # only set vars are reported
