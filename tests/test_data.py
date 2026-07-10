# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for ``give_me_a_sign.data.Data``."""

import json
from unittest.mock import mock_open

import pytest

import storage

from give_me_a_sign.data import Data


@pytest.fixture(autouse=True)
def reset_storage_stub():
    storage.reset()
    yield
    storage.reset()


@pytest.fixture
def data_without_restore(monkeypatch):
    monkeypatch.setattr(Data, "_restore", lambda self: False)
    return Data()


def test_set_get_round_trip(data_without_restore):
    store = data_without_restore
    store.set_item("weather", {"current": {"temperature": 72}})
    assert store.get_item("weather") == {"current": {"temperature": 72}}


def test_get_item_missing_returns_default(data_without_restore):
    store = data_without_restore
    assert store.get_item("missing") is None
    assert store.get_item("missing", 42) == 42


def test_is_updated_lifecycle(data_without_restore):
    store = data_without_restore
    assert store.is_updated("message") is False
    store.set_item("message", {"text": "hi"})
    assert store.is_updated("message") is True
    store.clear_updated("message")
    assert store.is_updated("message") is False


def test_clear_updated_missing_key(data_without_restore):
    store = data_without_restore
    store.clear_updated("missing")


def test_age_and_last_updated(data_without_restore, monkeypatch):
    store = data_without_restore
    assert store.last_updated("message") == 0

    times = iter([100.0, 125.0])
    monkeypatch.setattr("give_me_a_sign.data.time.time", lambda: next(times))

    store.set_item("message", {"text": "hi"})
    assert store.last_updated("message") == 100.0
    assert store.age("message") == 25


def test_timezone_triggers_save(data_without_restore, monkeypatch):
    store = data_without_restore
    writes = []

    class _CaptureWrite:
        def __init__(self, sink):
            self._sink = sink

        def write(self, payload):
            self._sink.append(payload)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("builtins.open", lambda path, mode="r": _CaptureWrite(writes))

    store.set_item("weather", {"current": {}})
    assert not storage.remount_calls

    store.set_item("timezone", {"timezone": "UTC", "transitions": []})
    assert storage.remount_calls == [("/", False), ("/", True)]
    assert len(writes) == 1


def test_restore_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "builtins.open",
        mock_open(read_data="not json"),
    )
    store = Data()
    assert store.get_item("message") is None


def test_restore_missing_file(monkeypatch):
    def _raise_oserror(*args, **kwargs):
        raise OSError("missing")

    monkeypatch.setattr("builtins.open", _raise_oserror)
    store = Data()
    assert store.get_item("message") is None


def test_restore_clears_dirty_flags_and_drops_empty_entries(monkeypatch):
    payload = {
        "message": {
            "data": {"text": "persisted"},
            "updated": True,
            "last_updated": 1,
        },
        "empty_shell": {
            "updated": False,
            "last_updated": 0,
        },
    }
    monkeypatch.setattr(
        "builtins.open",
        mock_open(read_data=json.dumps(payload)),
    )
    store = Data()
    assert store.get_item("message") == {"text": "persisted"}
    assert store.is_updated("message") is False
    assert "empty_shell" not in store.all()
