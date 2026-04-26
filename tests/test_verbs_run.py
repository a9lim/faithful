"""Tests for the `run` verb."""
from unittest.mock import MagicMock, patch

import pytest

from faithful.errors import FaithfulConfigError
from faithful.paths import ResolvedPaths
from faithful.verbs import run


def test_run_errors_when_no_config(tmp_path):
    paths = ResolvedPaths(
        home=tmp_path,
        config_path=tmp_path / "missing.toml",
        data_dir=tmp_path / "data",
    )
    with pytest.raises(FaithfulConfigError) as exc:
        run(paths)
    assert "No config" in str(exc.value)


@patch("faithful.bot.Faithful")
def test_run_starts_bot_when_config_exists(MockBot, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[discord]\ntoken = "tok"\nadmin_ids = [1]\n'
        '[backend]\napi_key = "k"\nmodel = "m"\n'
    )

    paths = ResolvedPaths(
        home=tmp_path,
        config_path=config_path,
        data_dir=tmp_path / "data",
    )

    instance = MagicMock()
    MockBot.return_value = instance

    code = run(paths)

    assert code == 0
    MockBot.assert_called_once()
    instance.run.assert_called_once_with("tok", log_handler=None)
