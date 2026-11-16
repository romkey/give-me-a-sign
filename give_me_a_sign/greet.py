# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/greet - greeter module for LED Matrix display
============================================================

* Author: John Romkey
"""

import os
import time
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
    ACTIVE_RENDER = "loop"

    # A name wider than the canvas scrolls left one pixel at a time, slowly
    # enough to read, holding at each end so both the start and the end of
    # the name are legible before it moves on.
    SCROLL_STEP_NS = 125_000_000
    SCROLL_HOLD_NS = 2_000_000_000

    def __init__(self, app):
        super().__init__(app)
        self._complications = None
        self._scroll = None

    def normalize_payload(self, endpoint, raw):  # pylint: disable=unused-argument
        return self.normalize_text_payload(raw, "person")

    def wants_interrupt(self) -> bool:
        if not self.store.is_updated(Greet.KEY):
            return False
        return True

    def _build_group(self):
        """
        Render the stored greeting, or None when there isn't a usable one.

        This renders whatever is in the store: the greet.full complication
        reuses it, so it must not depend on (or clear) the updated flag that
        :meth:`show` consumes for the interrupt. It does arm the name scroll
        for the label it builds, so :meth:`loop` scrolls whichever label is
        currently on screen.
        """
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

        self._start_scroll(line2)

        group = displayio.Group()
        group.append(line1)
        group.append(line2)
        return group

    def _start_scroll(self, label) -> None:
        """
        Arm (or disarm) the left scroll for the name on *label*.

        Only a name too wide for the canvas scrolls; anything that already
        fits is left where it is, and the scroll state is cleared so
        :meth:`loop` has nothing to do.
        """
        width = label.bounding_box[2]
        if width <= self._app.canvas_width:
            self._scroll = None
            return

        self._scroll = {
            "label": label,
            # The leftmost x that still keeps the end of the name on screen.
            "min_x": self._app.canvas_width - width,
            "next_time": time.monotonic_ns() + Greet.SCROLL_HOLD_NS,
        }

    def loop(self):
        """Advance the name scroll while the greeting is on display."""
        scroll = self._scroll
        if scroll is None:
            return

        now = time.monotonic_ns()
        if now < scroll["next_time"]:
            return

        label = scroll["label"]
        if label.x <= scroll["min_x"]:
            # The end of the name has been shown: start over from the left.
            label.x = 0
            scroll["next_time"] = now + Greet.SCROLL_HOLD_NS
            return

        label.x -= 1
        if label.x <= scroll["min_x"]:
            scroll["next_time"] = now + Greet.SCROLL_HOLD_NS
        else:
            scroll["next_time"] = now + Greet.SCROLL_STEP_NS

    def show(self) -> bool:
        # Greet is an interrupt: it shows once per pushed greeting, so the
        # updated flag is what gates and is consumed here, not in the render.
        if not self.store.is_updated(Greet.KEY):
            return False
        self.store.clear_updated(Greet.KEY)

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
