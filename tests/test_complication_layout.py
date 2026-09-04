# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Layout tests for the eighth-slot complications."""

import pytest
from adafruit_display_text.label import Label
from displayio import Group

from give_me_a_sign.aqi import AQI
from give_me_a_sign.clock import Clock
from give_me_a_sign.complication import EIGHTH
from give_me_a_sign.module import ModuleStore
from give_me_a_sign.uv import UV
from give_me_a_sign.weather import Weather


_WEATHER = {"current": {"temperature": 68, "humidity": 40}}


class _App:
    def __init__(self):
        self.canvas_width = 64
        self.canvas_height = 32
        self.modules = None


def _module(monkeypatch, cls, key, payload):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    module = cls(_App())
    module.store.set_item(key, payload)
    return module


@pytest.mark.parametrize(
    "cls,key,payload,layout",
    [
        (AQI, AQI.KEY, {"aqi": 42}, "eighth"),
        (UV, UV.KEY, {"index": 3.5}, "eighth"),
        (Weather, "weather", _WEATHER, "temp8"),
        (Weather, "weather", _WEATHER, "humidity8"),
    ],
)
def test_eighth_labels_sit_at_the_top_of_the_slot(
    monkeypatch, cls, key, payload, layout
):
    """
    A Label's y is not its top edge: the text starts bounding_box[1] rows
    above it (a negative number). Setting y = 0 therefore hangs the text off
    the top of the group, where it gets clipped.
    """
    module = _module(monkeypatch, cls, key, payload)
    group = module._build_group(layout)
    assert group is not None

    label = group[0]
    top_row = label.y + label.bounding_box[1]
    assert top_row == 0


class _ModuleRegistry:
    def __init__(self, clock):
        self._clock = clock

    def get(self, name):
        return self._clock if name == "clock" else None


class _StubClock:
    """Stands in for Clock so the test doesn't need the real bitmap fonts."""

    def __init__(self):
        self.label = Label(font=None, text="12:34")

    def mini_clock(self):
        return self.label


def test_append_mini_clock_keeps_the_whole_label_on_screen():
    """
    The mini clock sits flush in the top-right corner of the full screens:
    its first pixel row on 0 and its last column on the right edge.
    """
    app = _App()
    stub = _StubClock()
    app.modules = _ModuleRegistry(stub)

    group = Group()
    Clock.append_mini_clock(app, group)

    label = group[0]
    assert label.y + label.bounding_box[1] == 0
    assert label.x + label.bounding_box[2] == app.canvas_width


def test_append_mini_clock_without_a_clock_module():
    app = _App()
    app.modules = _ModuleRegistry(None)

    group = Group()
    Clock.append_mini_clock(app, group)
    assert len(group) == 0
