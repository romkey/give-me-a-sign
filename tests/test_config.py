# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for rotation config loading."""

import json

import pytest

from give_me_a_sign.config import DEFAULT_ROTATION, _default_rotation, load_config


class _Logger:
    def error(self, *_args, **_kwargs):
        pass


def test_default_rotation_matches_legacy_order():
    names = [entry["module"] for entry in DEFAULT_ROTATION]
    assert names == ["clock", "weather", "aqi", "uv", "pollen"]


def test_default_rotation_has_type():
    rotation = _default_rotation()
    assert all(entry["type"] == "module" for entry in rotation)
    assert rotation[0]["duration"] == 20


def test_missing_config_file(monkeypatch):
    def _raise_oserror(*_args, **_kwargs):
        raise OSError

    monkeypatch.setattr("builtins.open", _raise_oserror)
    config = load_config(_Logger())
    assert config["modules"] == []
    assert len(config["rotation"]) == 5


def test_valid_config_file(monkeypatch, tmp_path):
    config_data = {
        "modules": ["gmas_stocks"],
        "rotation": [{"module": "clock", "duration": 30}],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr("give_me_a_sign.config.CONFIG_FILE", str(config_path))

    config = load_config(_Logger())
    assert config["modules"] == ["gmas_stocks"]
    assert config["rotation"][0]["module"] == "clock"
    assert config["rotation"][0]["duration"] == 30


def test_invalid_json_returns_default(monkeypatch):
    class _FakeFile:
        def read(self):
            return "{not json"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: _FakeFile())
    config = load_config(_Logger())
    assert len(config["rotation"]) == 5
