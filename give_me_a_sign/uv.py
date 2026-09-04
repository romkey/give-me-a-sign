# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/uv - uv index module for LED Matrix display
==========================================================

* Author: John Romkey
"""

import displayio
import terminalio
import adafruit_display_text.label

from .clock import Clock
from .complication import EIGHTH, FULL, QUARTER, Complication
from .module import SignModule


class UV(SignModule):
    """
    Manages the display of UV Index on the sign.
    """

    NAME = "uv"
    KEY = "uv"
    ENDPOINTS = (KEY,)
    STALE_SECONDS = 60 * 60

    def __init__(self, app):
        super().__init__(app)
        self._complications = None

    def _index(self):
        uvi = self.store.get_item(UV.KEY)
        if uvi is None:
            return None
        try:
            index = float(uvi["index"])
        except (TypeError, KeyError, ValueError):
            return None
        if index == 0:
            return None
        return index

    def should_show(self) -> bool:
        if not super().should_show():
            return False
        clock = self._app.modules.get("clock")
        if clock is not None and clock.is_sundown:
            return False
        return self._index() is not None

    def _build_group(self, layout):
        index = self._index()
        if index is None:
            return None

        text = "UVI " + str(int(index * 10) / 10.0)
        group = displayio.Group()
        if layout == "full":
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=0x800080, text=text
            )
            line.x = 0
            line.y = 12
            group.append(line)
            Clock.append_mini_clock(self._app, group)
        elif layout == "quarter":
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=0x800080, text=text
            )
            line.x = 0
            line.y = 8
            group.append(line)
        elif layout == "eighth":
            compact = "UV" + str(int(index * 10) / 10.0)
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=0x800080, text=compact
            )
            line.x = 0
            line.y = 0
            group.append(line)
        return group

    def show(self) -> bool:
        self.store.clear_updated(UV.KEY)
        group = self._build_group("full")
        if group is None:
            return False
        self._app.show_group(group)
        return True

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication(
                    "full", FULL[0], FULL[1], lambda: self._build_group("full")
                ),
                Complication(
                    "quarter",
                    QUARTER[0],
                    QUARTER[1],
                    lambda: self._build_group("quarter"),
                ),
                Complication(
                    "eighth", EIGHTH[0], EIGHTH[1], lambda: self._build_group("eighth")
                ),
            ]
        return self._complications
