# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/ip - IP address module for LED Matrix display
====================================================

* Author: John Romkey
"""

import terminalio
from adafruit_display_text.scrolling_label import ScrollingLabel


class IP:
    """
    Queries and displays the sign's IP address, scrolling it if it's
    too wide for the display.
    """

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app
        self._line = None

    def show(self) -> bool:
        """
        Fetch the IP address from the ESP32 and then display it on the screen.
        """
        self._line = ScrollingLabel(
            terminalio.FONT,
            color=0x00FF00,
            text=str(self._app.platform.wifi_ip_address),
            max_characters=16,
            animate_time=1,
        )

        box = self._line.bounding_box
        width = box[2]
        if width > self._app.display.width:
            self._line.x = 0
        else:
            self._line.x = round((self._app.display.width - width) / 2)

        self._line.y = self._app.display.height // 2
        self._app.display.root_group = self._line

        return True

    def loop(self) -> None:
        """
        Advance the scrolling animation; called while the IP screen is shown
        """
        if self._line is not None:
            self._line.update()
