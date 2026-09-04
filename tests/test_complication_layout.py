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
def test_eighth_labels_fit_inside_the_slot(monkeypatch, cls, key, payload, layout):
    """
    Label y is the text's vertical center in this codebase, so a label at y=0
    hangs half of itself above the group and gets clipped.
    """
    module = _module(monkeypatch, cls, key, payload)
    group = module._build_group(layout)
    assert group is not None

    label = group[0]
    half_height = label.bounding_box[3] // 2
    assert label.y == EIGHTH[1] // 2
    assert label.y - half_height >= 0
    assert label.y + half_height <= EIGHTH[1]


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
    The mini clock sits flush in the top-right corner of the full screens.
    Label y is the text's vertical center, so a y below half the text height
    clipped the top row of pixels.
    """
    app = _App()
    stub = _StubClock()
    app.modules = _ModuleRegistry(stub)

    group = Group()
    Clock.append_mini_clock(app, group)

    label = group[0]
    half_height = label.bounding_box[3] // 2
    assert label.y - half_height >= 0
    assert label.x + label.bounding_box[2] == app.canvas_width


def test_append_mini_clock_without_a_clock_module():
    app = _App()
    app.modules = _ModuleRegistry(None)

    group = Group()
    Clock.append_mini_clock(app, group)
    assert len(group) == 0
