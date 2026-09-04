# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/greet - greeter module for LED Matrix display
============================================================

* Author: John Romkey
"""

import json
import os
import adafruit_display_text.label
import displayio
import terminalio

from .complication import FULL, Complication
from .module import SignModule


class Greet(SignModule):
    """
    Displays a greeting when notified that someone has entered the space.
    """

    NAME = "greet"
    KEY = "greet"
    ENDPOINTS = (KEY,)
    IS_INTERRUPT = True
    DEFAULT_DURATION = 15
    ACTIVE_RENDER = "once"

    def __init__(self, app):
        super().__init__(app)
        self._complications = None

    def normalize_payload(self, endpoint, raw):  # pylint: disable=unused-argument
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = None
        if not isinstance(data, dict):
            text = raw if data is None else data
            if not isinstance(text, str):
                text = str(text)
            return {"person": text}
        return data

    def wants_interrupt(self) -> bool:
        if not self.store.is_updated(Greet.KEY):
            return False
        return True

    def _build_group(self):
        if not self.store.is_updated(Greet.KEY):
            return None

        self.store.clear_updated(Greet.KEY)

        try:
            person = self.store.get_item(Greet.KEY)["person"]
        except (KeyError, TypeError):
            return None

        if not isinstance(person, str):
            return None

        names = person.split(" ")
        greet_msg = "Welcome"

        anonymize = os.getenv("anonymous_greetings")
        if anonymize is not None and person in anonymize.split(","):
            greet_msg = "Hi totally"
            names[0] = "human being"

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
                "key": "greet",
                "config": {
                    "name": "Greeting Text",
                    "endpoint": Greet.KEY,
                    "icon": "mdi:hand-wave",
                },
            }
        ]

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication("full", FULL[0], FULL[1], self._build_group),
            ]
        return self._complications
