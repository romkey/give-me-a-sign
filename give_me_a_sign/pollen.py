# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/pollen - pollen count module for LED Matrix display
====================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import displayio
import terminalio


class Pollen:
    """
    Manages the display of Pollen Count on the sign.

    The server receives Pollen Count values and stashes them in the Data store
    under the key "pollen". This class retrieves the count and displays it.

    Pollen Count has just the count value
    """

    KEY = "pollen"

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """

        self._app = app

    def show(self, mini_clock) -> bool:
        """
        Display the Pollen Count on the screen

        The server receives count and stashes it in the Data store under the key "pollen".
        This class retrieves count and displays it.

        Data structure should look like:

        .. code-block:: python
           { "pollen": integer }
        """

        pollen = self._app.data.get_item(Pollen.KEY)
        if pollen is None:
            return False

        self._app.data.clear_updated(Pollen.KEY)

        try:
            count = int(pollen["pollen"])
        except (KeyError, TypeError, ValueError):
            return False

        line = adafruit_display_text.label.Label(
            terminalio.FONT, color=0x800080, text="Pollen " + str(count)
        )
        line.x = 0
        line.y = 12

        group = displayio.Group()
        group.append(line)

        mini_clock_width = mini_clock.bounding_box[2]
        mini_clock.x = self._app.canvas_width - mini_clock_width
        mini_clock.y = 2
        group.append(mini_clock)

        self._app.show_group(group)

        return True

    def _draw_tree(self) -> None:
        """
        draw a tree - brown trunk green circle
        """
        # brown is 0xA52A2A

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
