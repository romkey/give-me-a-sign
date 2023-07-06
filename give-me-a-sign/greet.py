# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/greet - greeter module for LED Matrix display
====================================================

* Author: John Romkey
"""

from secrets import secrets  # pylint: disable=no-name-in-module

import adafruit_display_text.label
import displayio
import terminalio


class Greet:
    """
    Displays a greeting when notified that someone has entered the space.

    The server receives a greeting message and stashes it in the Data store under the key "greet".
    This class retrieves information and displays greets the person.

    Greetings have structured
    """

    KEY = "greet"

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app

    def show(self) -> bool:
        """
        Display the current greeting if valid.

        Greetings are stored in Data under the key "greet"

        Data structure should look like:

        .. code-block:: python
           { "person": string,
              "door": string
            }

        The person's name should be in the format "John R.", giving only the
        last initial and not the full name.
        """
        if not self._app.data.is_updated(Greet.KEY):
            print("not updated")
            return False

        self._app.data.clear_updated(Greet.KEY)

        try:
            person = self._app.data.get_item(Greet.KEY)["person"]
        except KeyError:
            return False

        # only use their first name
        names = person.split(" ")

        greet_msg = "Welcome"

        try:
            if person in secrets["anonymous_greetings"]:
                greet_msg = "Hi totally"
                names[0] = "human being"
        except KeyError:
            pass

        line1 = adafruit_display_text.label.Label(
            terminalio.FONT, color=0x00FF00, text=greet_msg
        )
        line1.x = 0
        line1.y = 8

        line2 = adafruit_display_text.label.Label(
            terminalio.FONT, color=0x0080FF, text=names[0]
        )
        line2.x = 0
        line2.y = 24

        group = displayio.Group()
        group.append(line1)
        group.append(line2)
        self._app.display.show(group)

        return True

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
