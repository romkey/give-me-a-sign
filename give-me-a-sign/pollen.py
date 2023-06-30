# SPDX-FileCopyrightText: 2023 John Romkey
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

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """

        self._app = app

    def show(self) -> bool:
        """
        Display the Pollen Count on the screen

        The server receives count and stashes it in the Data store under the key "count".
        This class retrieves count and displays it.

        Data structure should look like:

        .. code-block:: python
           { "count": integer }
        """

        pollen = self._app.data.get_item("pollen")
        if pollen is None:
            return False

        self._app.data.clear_updated("pollen")

        line = adafruit_display_text.label.Label(
            terminalio.FONT, color=0x800080, text="Pollen " + str(int(pollen["pollen"]))
        )
        line.x = 0
        line.y = 12

        g = displayio.Group()
        g.append(line)
        self._app.display.show(g)

        return True

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
