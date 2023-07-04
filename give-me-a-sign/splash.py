# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/splash - splash screen module for LED Matrix display
====================================================

* Author: John Romkey
"""

import displayio
import adafruit_imageload


class Splash:
    """
    Show a splash screen. Loads an image from /assets and displays it

    Supports BMP and GIF files
    """

    def __init__(self, app, filename):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app
        self._filename = filename

    def show(self) -> bool:
        """
        Load filename from flash and display it
        """
        try:
            bitmap, palette = adafruit_imageload.load(
                self._filename, bitmap=displayio.Bitmap, palette=displayio.Palette
            )
        except OSError:
            self._app.logger.error("Splash: OSError")
            return False
        except NotImplementedError:
            self._app.logger.error(f"Image {self._filename} unsupported")
            return False

        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        group = displayio.Group()
        group.append(tile_grid)
        self._app.display.show(group)
        return True

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
