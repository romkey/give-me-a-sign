# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/trimet - Trimet public transit module for LED Matrix display
====================================================

* Author: John Romkey
"""

import displayio
import terminalio
import adafruit_display_text.label


class Trimet:
    """
    Manages the display of Trimet info on the sign.

    The server receives Trimet data and stashes it in the Data store under the key "trimet".
    This class retrieves a message and displays it.

    Trimet data is an array of upcoming arrivals and departures with "shortSign" info on the
    line, the time, and an indication of the transportation type ("bus", "light rail", ...).
    """

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """

        self._app = app

    def show(self) -> bool:
        """
        Display Trimet on the screen

        The server receives index and stashes it in the Data store under the key "uv".
        This class retrieves index and displays it.

        Data structure should look like:

        .. code-block:: python
           { "index": integer }
        """

        trimet = self._app.data.get_item("trimet")
        self._app.data.clear_updated("trimet")

        if trimet is None or trimet["index"] == 0:
            return False

        try:
            line = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=0x800080,
                text="UVI " + str(int(trimet["index"] * 10) / 10.0),
            )
        except KeyError:
            return False

        line.x = 0
        line.y = 12

        group = displayio.Group()
        group.append(line)
        self._app.display.show(group)

        return True

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
