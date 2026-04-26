"""Tests for path resolution."""
from pathlib import Path


from faithful.paths import ResolvedPaths, ensure_home_exists, resolve_paths


def test_default_uses_home_faithful(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FAITHFUL_HOME", raising=False)

    paths = resolve_paths()

    assert paths.home == tmp_path / ".faithful"
    assert paths.config_path == tmp_path / ".faithful" / "config.toml"
    assert paths.data_dir == tmp_path / ".faithful" / "data"


def test_faithful_home_env_overrides_default(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "homedir")
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path / "envhome"))

    paths = resolve_paths()

    assert paths.home == tmp_path / "envhome"
    assert paths.config_path == tmp_path / "envhome" / "config.toml"
    assert paths.data_dir == tmp_path / "envhome" / "data"


def test_config_flag_overrides_env_and_default(monkeypatch, tmp_path):
    monkeypatch.setenv("FAITHFUL_HOME", str(tmp_path / "envhome"))

    custom = tmp_path / "custom.toml"
    paths = resolve_paths(config_override=custom)

    assert paths.config_path == custom
    # data_dir falls back to env home when only --config is given
    assert paths.data_dir == tmp_path / "envhome" / "data"


def test_data_dir_flag_overrides_env_and_default(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FAITHFUL_HOME", raising=False)

    custom = tmp_path / "datasomewhere"
    paths = resolve_paths(data_dir_override=custom)

    assert paths.data_dir == custom
    assert paths.config_path == tmp_path / ".faithful" / "config.toml"


def test_ensure_home_creates_directory(tmp_path):
    paths = ResolvedPaths(
        home=tmp_path / ".faithful",
        config_path=tmp_path / ".faithful" / "config.toml",
        data_dir=tmp_path / ".faithful" / "data",
    )

    ensure_home_exists(paths)

    assert paths.home.is_dir()
    assert paths.data_dir.is_dir()
