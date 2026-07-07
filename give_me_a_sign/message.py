# SPDX-FileCopyrightText: 2023-2026 John Romkey
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

    KEY = "message"

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
           { "text": string,
             "color": 0x000000,
             "duration": seconds
            }

        "duration" is optional (how long the sign shows the message;
        the state machine defaults to 15 seconds). Scrolling is not
        implemented.
        """

        self._app.data.clear_updated(Message.KEY)

        message = self._app.data.get_item(Message.KEY)
        try:
            text = message["text"]
            # color is optional so HA plain-text "Message Text" works
            color = message.get("color", 0xFFFFFF)
        except (KeyError, TypeError, AttributeError):
            print("message: bad data", message)
            return False

        line = Label(
            terminalio.FONT,
            color=color,
            text=text,
        )

        box = line.bounding_box
        width = box[2]
        if width > self._app.canvas_width:
            line.x = 0
        else:
            line.x = round((self._app.canvas_width - width) / 2)

        line.y = self._app.canvas_height // 2

        group = displayio.Group()
        group.append(line)
        self._app.show_group(group)
        return True

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
