# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/nyan - animated Nyan Cat module for LED Matrix display
====================================================

* Author: John Romkey
"""

import gifio
import displayio

from ._paths import ASSETS_DIR

# based on https://learn.adafruit.com/using-animated-gif-files-in-circuitpython/gifio


class Nyan:
    """
    Manages the display of animated Nyan Cat
    """

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app
        self._odg = gifio.OnDiskGif(ASSETS_DIR + "/nyan-cat-animation-sm.gif")

    def show(self, mini_clock) -> bool:
        """
        Display the first frame of the Nyan Cat animation.
        """
        _ = mini_clock
        try:
            self._odg.seek_frame(0)
        except (OSError, RuntimeError):
            return False

        group = displayio.Group()
        tile_grid = displayio.TileGrid(
            self._odg.bitmap, pixel_shader=self._odg.pixel_shader
        )
        group.append(tile_grid)
        self._app.display.root_group = group
        return True
