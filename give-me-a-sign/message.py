# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/message - text message module for LED Matrix display
====================================================

* Author: John Romkey
"""

import displayio
import terminalio
from adafruit_display_text.label import Label


class Message:
    """
    Manages the display of messages sent to the sign.

    The server receives messages and stashes them in the Data store under the key "message".
    This class retrieves a message and displays it.

    Messages have text and an RGB color.
    """

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """

        self._app = app

    def show(self) -> bool:
        """
        Display the message on the screen

        The server receives weather conditions them in the Data store under the key "message".
        This class retrieves a message and displays it.

        Data structure should look like:

        .. code-block:: python
           { "message": text,
             "color": 0x000000,
             "duration": seconds,
             "scroll": true/false
            }
        """

        self._app.data.clear_updated("message")

        try:
            line = Label(
                terminalio.FONT,
                color=self._app.data.get_item("message")["color"],
                text=self._app.data.get_item("message")["text"],
            )
        except KeyError:
            print("message: bad data", self._app.data.get_item("message"))
            return False

        box = line.bounding_box
        width = box[2]
        if width > self._app.display.width:
            line.x = 0
        else:
            line.x = round((self._app.display.width - width) / 2)

        line.y = self._app.display.height // 2

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
