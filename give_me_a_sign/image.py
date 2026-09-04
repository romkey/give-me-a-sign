# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/image - image module for LED Matrix display
==========================================================

* Author: John Romkey
"""

import displayio
import adafruit_imageload

from .complication import FULL, Complication
from .module import SignModule


class Image(SignModule):
    """
    Retrieve information about an image from Data and display it.
    """

    NAME = "image"
    KEY = "image"
    ENDPOINTS = (KEY,)
    IS_INTERRUPT = True
    DEFAULT_DURATION = 15
    ACTIVE_RENDER = "once"

    def __init__(self, app):
        super().__init__(app)
        self._complications = None

    def _load_image(self):
        image = self.store.get_item(Image.KEY)
        self.store.clear_updated(Image.KEY)

        try:
            if image is None or image["filename"] is None:
                return None, False
        except (KeyError, TypeError):
            return None, False

        try:
            bitmap, palette = adafruit_imageload.load(
                image["filename"], bitmap=displayio.Bitmap, palette=displayio.Palette
            )
        except (OSError, NotImplementedError, TypeError):
            return None, False

        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        group = displayio.Group()
        group.append(tile_grid)

        if (
            bitmap.width <= self._app.canvas_width
            and bitmap.height <= self._app.canvas_height
        ):
            tile_grid.x = (self._app.canvas_width - bitmap.width) // 2
            tile_grid.y = (self._app.canvas_height - bitmap.height) // 2
            return group, False

        tile_grid.x = max(0, (self._app.display.width - bitmap.width) // 2)
        tile_grid.y = max(0, (self._app.display.height - bitmap.height) // 2)
        return group, True

    def _build_group(self):
        group, _ = self._load_image()
        return group

    def show(self) -> bool:
        group, use_full_display = self._load_image()
        if group is None:
            return False
        if use_full_display:
            self._app.display.root_group = group
        else:
            self._app.show_group(group)
        return True

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication("full", FULL[0], FULL[1], self._build_group),
            ]
        return self._complications
