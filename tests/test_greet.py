# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for greet anonymization and validation."""

from types import SimpleNamespace

import pytest

from give_me_a_sign.data import Data
from give_me_a_sign.greet import Greet


class _App:
    def __init__(self):
        self.data = Data()
        self.canvas_width = 64
        self.canvas_height = 32
        self._shown = None

    def show_group(self, group):
        self._shown = group


@pytest.fixture
def greeter(monkeypatch):
    monkeypatch.setattr(Data, "_restore", lambda self: False)
    app = _App()
    return Greet(app), app


def _publish_greet(app, payload):
    app.data.set_item(Greet.KEY, payload)
    app.data._data[Greet.KEY][Data.KEY_UPDATED] = True


def test_greet_named_person(greeter):
    greet, app = greeter
    _publish_greet(app, {"person": "John R."})
    assert greet.show() is True
    assert app._shown[0].text == "Welcome"
    assert app._shown[1].text == "John"


def test_greet_anonymous(monkeypatch, greeter):
    greet, app = greeter
    monkeypatch.setenv("anonymous_greetings", "Person A.,Person B.")
    _publish_greet(app, {"person": "Person A."})
    assert greet.show() is True
    assert app._shown[0].text == "Hi totally"
    assert app._shown[1].text == "human being"


def test_greet_missing_person(greeter):
    greet, app = greeter
    _publish_greet(app, {"door": "front"})
    assert greet.show() is False


def test_greet_non_string_person(greeter):
    greet, app = greeter
    _publish_greet(app, {"person": 5})
    assert greet.show() is False
