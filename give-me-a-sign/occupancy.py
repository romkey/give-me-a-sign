# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/occupancy - indicates which areas of PDX Hackerspace
are currently occupied
====================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import displayio
import terminalio


class Occupancy:
    """
    Manages the display of UV Index on the sign.

    The server receives UV Index values and stashes them in the Data store under the key "uv".
    This class retrieves a message and displays it.

    UV Index has just the index value
    """

    ROOM_UNIT1_FRONT = "1f"
    ROOM_UNIT1_BACK = "1b"
    ROOM_UNIT2_FRONT = "2f"
    ROOM_UNIT2_BACK = "2f"
    ROOM_ELECTRONICS_LAB = "el"
    ROOM_CRAFT_LAB = "cl"
    ROOM_LASER_LAB = "ll"
    ROOM_KITCHEN = "k"
    ROOM_WOODSHOP_FRONT = "wsf"
    ROOM_WOODSHOP_BACK = "wsb"
    ROOM_BACK_YARD = "by"

    ROOM_LOCS = {
        "1f": {"x": 0, "y": 0},
        "1b": {"x": 0, "y": 0},
        "2f": {"x": 0, "y": 0},
        "2b": {"x": 0, "y": 0},
        "el": {"x": 0, "y": 0},
        "cl": {"x": 0, "y": 0},
        "ll": {"x": 0, "y": 0},
        "k": {"x": 0, "y": 0},
        "wsf": {"x": 0, "y": 0},
        "wsb": {"x": 0, "y": 0},
        "by": {"x": 0, "y": 0},
    }

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app

    def show(self) -> bool:
        """
        Display the UV Index on the screen

        The server receives index and stashes it in the Data store under the key "uv".
        This class retrieves index and displays it.

        Data structure should look like:

        .. code-block:: python
           { "index": integer }
        """
        occupancy = self._app.data.get_item("occupancy")
        if occupancy is None:
            return False

        self._app.data.clear_updated("occupancy")

        line1 = adafruit_display_text.label.Label(
            terminalio.FONT, color=0xFF0000, text="Hello"
        )
        line1.x = 0
        line1.y = 8

        # Put each line of text into a Group, then show that group.
        group = displayio.Group()
        group.append(line1)
        self._app.display.show(group)

        return True

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        self._app.display.refresh(minimum_frames_per_second=0)
