# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for clock timezone and solar logic."""

from types import SimpleNamespace

import pytest

from give_me_a_sign.clock import Clock
from give_me_a_sign.data import Data


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message, *args):
        self.errors.append(message)

    def info(self, message, *args):
        pass


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(Data, "_restore", lambda self: False)
    app = SimpleNamespace()
    app.data = Data()
    app.logger = _Logger()

    instance = Clock.__new__(Clock)
    instance._app = app
    instance._timezone_breaks = None
    instance._timezone_cache_until = 0
    instance._timezone_cached_offset = 0
    instance._solar_prev_sunrise = None
    return instance


def _set_solar(clock, now, sunrise_delta, sunset_delta):
    clock._app.data.set_item(
        Clock.KEY_SOLAR,
        {
            "sunrise": now + sunrise_delta,
            "sunset": now + sunset_delta,
        },
    )


def test_timezone_offset_selects_latest_transition(clock, monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr("give_me_a_sign.clock.time.time", lambda: now)

    clock._app.data.set_item(
        Clock.KEY_TIMEZONE,
        {
            "timezone": "America/Los_Angeles",
            "transitions": [
                {"timestamp": now - 7200, "offset": -28800},
                {"timestamp": now + 3600, "offset": -25200},
            ],
        },
    )
    clock._app.data._data[Clock.KEY_TIMEZONE][Data.KEY_UPDATED] = True

    clock._check_timezone_offset()
    assert clock.timezone_offset == -28800
    assert clock._timezone_cache_until == now + 3600


def test_timezone_update_invalidates_cache(clock, monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr("give_me_a_sign.clock.time.time", lambda: now)

    clock._timezone_cache_until = now + 99999
    clock._timezone_cached_offset = 123
    clock._app.data.set_item(
        Clock.KEY_TIMEZONE,
        {
            "timezone": "UTC",
            "transitions": [{"timestamp": now - 60, "offset": 0}],
        },
    )
    clock._app.data._data[Clock.KEY_TIMEZONE][Data.KEY_UPDATED] = True

    clock._check_timezone_offset()
    assert clock.timezone_offset == 0


def test_timezone_empty_transitions(clock, monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr("give_me_a_sign.clock.time.time", lambda: now)

    clock._app.data.set_item(
        Clock.KEY_TIMEZONE,
        {"timezone": "UTC", "transitions": []},
    )
    clock._app.data._data[Clock.KEY_TIMEZONE][Data.KEY_UPDATED] = True

    clock._check_timezone_offset()
    assert clock.timezone_offset == 0


def test_calculate_color_no_solar(clock):
    assert clock._calculate_color(1_700_000_000) == Clock.NO_SOLAR_COLOR


def test_calculate_color_missing_keys(clock):
    clock._app.data.set_item(Clock.KEY_SOLAR, {"sunrise": 1})
    assert clock._calculate_color(1_700_000_000) == Clock.NO_SOLAR_COLOR
    assert clock._app.logger.errors


def test_calculate_color_day(clock):
    now = 1_700_000_000
    _set_solar(clock, now, -4 * 3600, 4 * 3600)
    assert clock._calculate_color(now) == Clock.COLOR_DAY


def test_calculate_color_pre_sunset(clock):
    now = 1_700_000_000
    _set_solar(clock, now, -4 * 3600, 30 * 60)
    assert clock._calculate_color(now) == Clock.COLOR_PRE_SUNSET


def test_calculate_color_night(clock):
    now = 1_700_000_000
    _set_solar(clock, now, 10 * 3600, -2 * 3600)
    assert clock._calculate_color(now) == Clock.COLOR_NIGHT


def test_calculate_color_pre_sunrise(clock):
    now = 1_700_000_000
    _set_solar(clock, now, 30 * 60, 8 * 3600)
    assert clock._calculate_color(now) == Clock.COLOR_PRE_SUNRISE


def test_calculate_color_ha_next_event_day(clock):
    now = 1_700_000_000
    clock._app.data.set_item(
        Clock.KEY_SOLAR,
        {
            "sunrise": now + 20 * 3600,
            "sunset": now + 6 * 3600,
        },
    )
    assert clock._calculate_color(now) == Clock.COLOR_DAY


def test_is_sundown_before_sunset(clock):
    now = 1_700_000_000
    _set_solar(clock, now, -4 * 3600, 20 * 60)
    assert clock.is_sundown is True


def test_is_sundown_night_normal_order(clock):
    now = 1_700_000_000
    _set_solar(clock, now, -14 * 3600, -2 * 3600)
    assert clock.is_sundown is True


def test_is_sundown_ha_next_event_day(clock):
    now = 1_700_000_000
    clock._app.data.set_item(
        Clock.KEY_SOLAR,
        {
            "sunrise": now + 28 * 3600,
            "sunset": now + 4 * 3600,
        },
    )
    assert clock.is_sundown is False


def test_is_sundown_without_solar(clock):
    assert clock.is_sundown is False
