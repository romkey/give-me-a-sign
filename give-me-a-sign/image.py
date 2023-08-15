# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/image - image module for LED Matrix display
====================================================

* Author: John Romkey
"""

import displayio
import adafruit_imageload


class Image:
    """
    Retrieve information about an image from Data
    Display the image at the correct location for the specified duration
    """

    KEY = "image"

    def __init__(self, app):
        self._app = app

    def show(self) -> bool:
        """
        Get image info from Data, key "image"
        display it or return False to indicate there's nothing to do
        """
        image = self._app.data.get_item(Image.KEY)
        self._app.data.clear_updated(Image.KEY)

        try:
            if image is None or image["filename"] is None:
                return False
        except KeyError:
            return False

        try:
            bitmap, palette = adafruit_imageload.load(
                image["filename"], bitmap=displayio.Bitmap, palette=displayio.Palette
            )
        except OSError:
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
