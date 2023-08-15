# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/aqi - air quality index module for LED Matrix display
====================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import displayio
import terminalio


class AQI:
    """
    Manages the display of Air Quality Index on the sign.

    The server receives Air Quality Index values and stashes them
    in the Data store under the key "aqi".

    This class retrieves a message and displays it.

    Air Quality Index has just the index value
    """

    KEY = "aqi"

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """

        self._app = app

    def show(self, mini_clock) -> bool:
        """
        Display the Air Quality Index on the screen

        The server receives index and stashes it in the Data store under the key "aqi".
        This class retrieves index and displays it.

        Data structure should look like:

        .. code-block:: python
           { "index": integer }
        """
        aqi = self._app.data.get_item(AQI.KEY)
        if aqi is None:
            return False

        self._app.data.clear_updated(AQI.KEY)
        index = int(aqi["aqi"])

        line = adafruit_display_text.label.Label(
            terminalio.FONT, color=AQI._aqi_color(index), text="AQI " + str(index)
        )
        line.x = 0
        line.y = 12

        group = displayio.Group()
        group.append(line)

        mini_clock_width = mini_clock.bounding_box[2]
        mini_clock.x = 64 - mini_clock_width
        mini_clock.y = 2
        group.append(mini_clock)

        self._app.display.show(group)

        return True

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return

    @staticmethod
    def _aqi_color(aqi) -> int:
        """
        Returns the color associated with a particular Air Quality Index

        0 to 50 - green
        51 to 100 - yellow
        101 to 150 - orange
        151 to 200 - red
        201 to 300 - purple
        301 and up - maroon

        source: https://www.airnow.gov/aqi/aqi-basics/
        """
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
