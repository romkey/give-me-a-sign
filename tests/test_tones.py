# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for tone payload validation."""

from types import SimpleNamespace

import pytest

import pwmio

from give_me_a_sign.data import Data
from give_me_a_sign.tones import Tones


@pytest.fixture
def tones_player(monkeypatch):
    monkeypatch.setattr(Data, "_restore", lambda self: False)
    pwmio.PWMOut.reset()
    app = SimpleNamespace()
    app.data = Data()
    return Tones(app), app


def test_play_valid_tones(tones_player):
    player, app = tones_player
    app.data.set_item(
        Tones.KEY,
        {
            "tones": [
                {"frequency": "440", "duration": "0.5", "volume": "100"},
                {"frequency": 880, "duration": 0.25, "volume": 50},
            ]
        },
    )
    app.data._data[Tones.KEY][Data.KEY_UPDATED] = True

    assert player.play() is True
    assert player._tones == [(440, 0.5, 100.0), (880, 0.25, 50.0)]


def test_play_missing_tones_key(tones_player):
    player, app = tones_player
    app.data.set_item(Tones.KEY, {})
    app.data._data[Tones.KEY][Data.KEY_UPDATED] = True

    assert player.play() is False
    assert player._current_index is None


def test_play_bad_tone_entry(tones_player):
    player, app = tones_player
    app.data.set_item(
        Tones.KEY,
        {"tones": [{"frequency": 440, "duration": 0.5}]},
    )
    app.data._data[Tones.KEY][Data.KEY_UPDATED] = True

    assert player.play() is False
    assert player._current_index is None
