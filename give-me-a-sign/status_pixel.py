# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/mqtt - MQTT support for Give Me A Sign
====================================================

* Author: John Romkey
"""
import displayio


class StatusPixel:
    """
    StatusPixel displays a pixel in the upper right corner that indicates the status
    of the network
    """

    OKAY = 0
    NO_WIFI = 1
    NO_MQTT = 2

    def __init__(self, app):
        self._app = app
        self._bitmap = displayio.Bitmap(1, 1, 4)
        self._palette = displayio.Palette(4)
        self._palette[StatusPixel.OKAY] = 0x000000  # black
        self._palette[StatusPixel.NO_WIFI] = 0xFF0000  # red - no WiFi
        self._palette[StatusPixel.NO_MQTT] = 0x00FF00  # blue - no MQTT
        self._palette.make_transparent(StatusPixel.OKAY)

    def loop(self):
        """
        Loop processing - check status to determine pixel state
        """
        if not self._app.platform.mqtt_is_connected:
            self._bitmap[0, 0] = StatusPixel.NO_MQTT
            return

        if not self._app.platform.wifi_is_connected:
            self._bitmap[0, 0] = StatusPixel.NO_WIFI
            return

        self._bitmap[0, 0] = StatusPixel.OKAY
