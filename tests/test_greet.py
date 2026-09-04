# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for greet anonymization and validation."""

from types import SimpleNamespace

import pytest

from give_me_a_sign.greet import Greet
from give_me_a_sign.module import ModuleStore


class _App:
    def __init__(self):
        self.canvas_width = 64
        self.canvas_height = 32
        self._shown = None

    def show_group(self, group):
        self._shown = group


@pytest.fixture
def greeter(monkeypatch):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    app = _App()
    return Greet(app), app


def _publish_greet(greet, payload):
    greet.store.set_item(Greet.KEY, payload)
    greet.store._data[Greet.KEY][ModuleStore.KEY_UPDATED] = True


def test_greet_named_person(greeter):
    greet, app = greeter
    _publish_greet(greet, {"person": "John R."})
    assert greet.show() is True
    assert app._shown[0].text == "Welcome"
    assert app._shown[1].text == "John"


def test_greet_anonymous(monkeypatch, greeter):
    greet, app = greeter
    monkeypatch.setenv("anonymous_greetings", "Person A.,Person B.")
    _publish_greet(greet, {"person": "Person A."})
    assert greet.show() is True
    assert app._shown[0].text == "Hi totally"
    assert app._shown[1].text == "human being"


def test_greet_missing_person(greeter):
    greet, _ = greeter
    _publish_greet(greet, {"door": "front"})
    assert greet.show() is False


def test_greet_non_string_person(greeter):
    greet, _ = greeter
    _publish_greet(greet, {"person": 5})
    assert greet.show() is False


def test_greet_shows_once_per_greeting(greeter):
    greet, _ = greeter
    _publish_greet(greet, {"person": "John R."})
    assert greet.show() is True
    assert greet.show() is False


def test_greet_complication_renders_after_the_interrupt(greeter):
    """
    show() consumes the updated flag for the interrupt. The greet.full
    complication reuses _build_group, so it must still paint the stored
    greeting on a composed screen afterwards.
    """
    greet, _ = greeter
    _publish_greet(greet, {"person": "John R."})
    assert greet.show() is True

    full = greet.complications()[0]
    assert full.name == "full"

    group = full.render()
    assert group is not None
    assert group[0].text == "Welcome"
    assert group[1].text == "John"


def test_greet_complication_without_data(greeter):
    greet, _ = greeter
    assert greet.complications()[0].render() is None
