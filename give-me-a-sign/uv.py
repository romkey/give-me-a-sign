# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/uv - uv index module for LED Matrix display
====================================================

* Author: John Romkey
"""

import displayio
import terminalio
import adafruit_display_text.label


class UV:
    """
    Manages the display of UV Index on the sign.

    The server receives UV Index values and stashes them in the Data store under the key "uv".
    This class retrieves a message and displays it.

    UV Index has just the index value
    """

    KEY = "uv"

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """

        self._app = app

    def show(self, mini_clock) -> bool:
        """
        Display the UV Index on the screen

        The server receives index and stashes it in the Data store under the key "uv".
        This class retrieves index and displays it.

        Data structure should look like:

        .. code-block:: python
           { "index": integer }
        """

        uvi = self._app.data.get_item(UV.KEY)
        self._app.data.clear_updated(UV.KEY)

        if uvi is None or uvi["index"] == 0:
            return False

        try:
            line = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=0x800080,
                text="UVI " + str(int(uvi["index"] * 10) / 10.0),
            )
        except KeyError:
            return False

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
