# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/complication - fractional screen rendering and composition
=========================================================================

* Author: John Romkey
"""

import displayio

CANVAS_WIDTH = 64
CANVAS_HEIGHT = 32

FULL = (CANVAS_WIDTH, CANVAS_HEIGHT)
HALF_WIDE = (CANVAS_WIDTH, CANVAS_HEIGHT // 2)
HALF_TALL = (CANVAS_WIDTH // 2, CANVAS_HEIGHT)
QUARTER = (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2)
EIGHTH = (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 4)


class Complication:  # pylint: disable=too-few-public-methods
    """
    Descriptor for a fractional rendering of a module's data.
    """

    def __init__(self, name, width, height, render_fn):
        self.name = name
        self.width = width
        self.height = height
        self._render_fn = render_fn

    def render(self):
        """Build and return this complication's displayio group."""
        return self._render_fn()


class Composer:
    """
    Build a displayio.Group from complication refs in a composed-screen config entry.
    """

    def __init__(self, app):
        self._app = app

    def show(self, screen_entry) -> bool:
        """Compose and display the complications listed in *screen_entry*."""
        group = displayio.Group()
        rendered = 0

        for comp in screen_entry["complications"]:
            complication = self._resolve(comp["ref"])
            if complication is None:
                self._app.logger.error(f"composer: unknown ref {comp['ref']}")
                continue

            slot = complication.render()
            if slot is None:
                continue

            x = comp["x"]
            y = comp["y"]
            if x < 0 or y < 0:
                continue
            if x + complication.width > CANVAS_WIDTH:
                continue
            if y + complication.height > CANVAS_HEIGHT:
                continue

            slot.x = x
            slot.y = y
            group.append(slot)
            rendered += 1

        if rendered == 0:
            return False

        self._app.show_group(group)
        return True

    def _resolve(self, ref):
        if "." not in ref:
            return None
        module_name, comp_name = ref.split(".", 1)
        module = self._app.modules.get(module_name)
        if module is None:
            return None
        for complication in module.complications():
            if complication.name == comp_name:
                return complication
        return None
