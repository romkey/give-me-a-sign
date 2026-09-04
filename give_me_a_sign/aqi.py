# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/aqi - air quality index module for LED Matrix display
====================================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import displayio
import terminalio

from .clock import Clock
from .complication import EIGHTH, FULL, QUARTER, Complication
from .module import SignModule


class AQI(SignModule):
    """
    Manages the display of Air Quality Index on the sign.
    """

    NAME = "aqi"
    KEY = "aqi"
    ENDPOINTS = (KEY,)
    STALE_SECONDS = 60 * 60

    def __init__(self, app):
        super().__init__(app)
        self._complications = None

    def _index(self):
        aqi = self.store.get_item(AQI.KEY)
        if aqi is None:
            return None
        try:
            return int(aqi["aqi"])
        except (KeyError, TypeError, ValueError):
            return None

    def _build_group(self, layout):
        index = self._index()
        if index is None:
            return None

        group = displayio.Group()
        if layout == "full":
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=AQI._aqi_color(index), text="AQI " + str(index)
            )
            line.x = 0
            line.y = 12
            group.append(line)
            Clock.append_mini_clock(self._app, group)
        elif layout == "quarter":
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=AQI._aqi_color(index), text="AQI " + str(index)
            )
            line.x = 0
            line.y = 8
            group.append(line)
        elif layout == "eighth":
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=AQI._aqi_color(index), text="AQI" + str(index)
            )
            line.x = 0
            # Label y is the text's vertical center, so center it in the slot.
            line.y = EIGHTH[1] // 2
            group.append(line)
        return group

    def show(self) -> bool:
        self.store.clear_updated(AQI.KEY)
        group = self._build_group("full")
        if group is None:
            return False
        self._app.show_group(group)
        return True

    @staticmethod
    def _aqi_color(aqi) -> int:
        if aqi > 300:
            return 0x800000
        if aqi > 200:
            return 0x800080
        if aqi > 150:
            return 0xFF0000
        if aqi > 100:
            return 0xFFA500
        if aqi > 50:
            return 0xFFFF00
        return 0x00FF00

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
