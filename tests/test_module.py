# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for SignModule and ModuleStore."""

import pytest

from give_me_a_sign.module import ModuleStore, SignModule


class _SampleModule(SignModule):
    NAME = "sample"
    ENDPOINTS = ("sample",)
    STALE_SECONDS = 60
    DEFAULT_DURATION = 15


class _PlainTextModule(SignModule):
    NAME = "plain"
    ENDPOINTS = ("plain",)

    def normalize_payload(self, endpoint, raw):  # pylint: disable=unused-argument
        if raw == "bad":
            return None
        return {"value": raw}


class _Logger:
    def error(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass


class _App:
    def __init__(self):
        self.logger = _Logger()


@pytest.fixture
def module(monkeypatch):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    return _SampleModule(_App())


def test_receive_stores_json(module):
    module.receive("sample", '{"value": 1}')
    assert module.store.get_item("sample") == {"value": 1}
    assert module.store.is_updated("sample") is True


def test_receive_rejects_bad_payload(module):
    bad = _PlainTextModule(module._app)
    bad.receive("plain", "bad")
    assert bad.store.has_item("plain") is False


def test_is_stale(module, monkeypatch):
    monkeypatch.setattr("give_me_a_sign.module.time.time", lambda: 1000)
    module.store.set_item("sample", {"value": 1})
    monkeypatch.setattr("give_me_a_sign.module.time.time", lambda: 2000)
    assert module.is_stale() is True


def test_duration_default(module):
    module.store.set_item("sample", {"value": 1})
    assert module.duration() == 15


def test_duration_from_payload(module):
    module.store.set_item("sample", {"value": 1, "duration": 30})
    assert module.duration() == 30


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"person": "John R."}', {"person": "John R."}),
        ('{"door": "front"}', {"door": "front"}),
        ("John R.", {"person": "John R."}),
        ('"John R."', {"person": "John R."}),
        ("5", {"person": "5"}),
        ("[1, 2]", {"person": "[1, 2]"}),
    ],
)
def test_normalize_text_payload(raw, expected):
    """
    greet and message both accept plain text as well as JSON. A JSON object
    passes through; anything else becomes {key: text}.
    """
    assert SignModule.normalize_text_payload(raw, "person") == expected


def test_normalize_text_payload_uses_the_given_key():
    assert SignModule.normalize_text_payload("hello", "text") == {"text": "hello"}
