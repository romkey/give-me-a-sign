# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/message - text message module for LED Matrix display
===================================================================

* Author: John Romkey
"""

import displayio
import terminalio
from adafruit_display_text.label import Label

from .complication import FULL, Complication
from .module import SignModule


class Message(SignModule):
    """
    Manages the display of messages sent to the sign.
    """

    NAME = "message"
    KEY = "message"
    ENDPOINTS = (KEY,)
    IS_INTERRUPT = True
    DEFAULT_DURATION = 15
    ACTIVE_RENDER = "once"

    def __init__(self, app):
        super().__init__(app)
        self._complications = None

    def normalize_payload(self, endpoint, raw):  # pylint: disable=unused-argument
        data = self.normalize_text_payload(raw, "text")

        # Home Assistant's notify payloads carry the body under "message".
        if "text" not in data and isinstance(data.get("message"), str):
            return {"text": data["message"]}
        return data

    def _build_group(self):
        message = self.store.get_item(Message.KEY)
        self.store.clear_updated(Message.KEY)
        try:
            text = message["text"]
            color = message.get("color", 0xFFFFFF)
        except (KeyError, TypeError, AttributeError):
            print("message: bad data", message)
            return None

        line = Label(terminalio.FONT, color=color, text=text)
        box = line.bounding_box
        width = box[2]
        if width > self._app.canvas_width:
            line.x = 0
        else:
            line.x = round((self._app.canvas_width - width) / 2)
        line.y = self._app.canvas_height // 2

        group = displayio.Group()
        group.append(line)
        return group

    def show(self) -> bool:
        group = self._build_group()
        if group is None:
            return False
        self._app.show_group(group)
        return True

    def ha_entities(self):
        return [
            {
                "component": "text",
                "key": "message",
                "config": {
                    "name": "Message Text",
                    "endpoint": Message.KEY,
                    "icon": "mdi:message-text",
                },
            }
        ]

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication("full", FULL[0], FULL[1], self._build_group),
            ]
        return self._complications
