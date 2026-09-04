# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
Example external module implementation.
"""

import displayio
import terminalio
from adafruit_display_text.label import Label

from give_me_a_sign.complication import EIGHTH, FULL, Complication
from give_me_a_sign.module import SignModule


class ExampleModule(SignModule):
    NAME = "example"
    ENDPOINTS = ("example",)
    DEFAULT_DURATION = 8

    def __init__(self, app):
        super().__init__(app)
        self._complications = None

    def _text(self):
        payload = self.store.get_item("example")
        if not isinstance(payload, dict):
            return None
        text = payload.get("text")
        if not isinstance(text, str) or not text:
            return None
        return text

    def _build_group(self, layout):
        text = self._text()
        if text is None:
            return None

        group = displayio.Group()
        if layout == "full":
            label = Label(terminalio.FONT, color=0x00FFFF, text=text[:12])
            label.x = 0
            label.y = 12
            group.append(label)
        else:
            label = Label(terminalio.FONT, color=0x00FFFF, text=text[:8])
            label.x = 0
            label.y = 0
            group.append(label)
        return group

    def show(self) -> bool:
        self.store.clear_updated("example")
        group = self._build_group("full")
        if group is None:
            return False
        self._app.show_group(group)
        return True

    def ha_entities(self):  # pylint: disable=no-self-use
        return [
            {
                "component": "text",
                "key": "example",
                "config": {
                    "name": "Example Text",
                    "endpoint": "example",
                    "icon": "mdi:star",
                },
            }
        ]

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication(
                    "full", FULL[0], FULL[1], lambda: self._build_group("full")
                ),
                Complication(
                    "eighth", EIGHTH[0], EIGHTH[1], lambda: self._build_group("eighth")
                ),
            ]
        return self._complications
