# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/pollen - pollen count module for LED Matrix display
====================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import displayio
import terminalio

_BROWN = 0xA52A2A
_GREEN = 0x00FF00
_TEXT_COLOR = 0x800080
_ICON_X = 0
_TEXT_X = 10
_TREE_Y = 8
_GRASS_Y = 24
_TREE_ICON_Y = 0
_GRASS_ICON_Y = 16

_TREE_PIXELS = (
    "..22..",
    ".2222.",
    "222222",
    "...1..",
    "...1..",
    "..11..",
)

_GRASS_PIXELS = (
    "......",
    ".1..1.",
    ".11.1.",
    "11.111",
    "111111",
    ".1111.",
)


class Pollen:
    """
    Manages the display of Pollen Count on the sign.

    The server receives Pollen Count values and stashes them in the Data store
    under the key "pollen". This class retrieves the counts and displays them.

    Tree and grass counts are shown on separate lines with a small icon for each.
    """

    KEY = "pollen"

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """

        self._app = app
        self._tree_icon = Pollen._make_icon(_TREE_PIXELS, (_BROWN, _GREEN))
        self._grass_icon = Pollen._make_icon(_GRASS_PIXELS, (_GREEN,))

    def show(self, mini_clock) -> bool:
        """
        Display pollen counts on the screen.

        The server stashes counts in the Data store under the key "pollen".
        This class retrieves them and displays tree and grass on separate lines.

        Data structure should look like:

        .. code-block:: python
           { "tree": integer, "grass": integer }

        Either key may be omitted; the screen is shown when at least one count
        is present.
        """

        pollen = self._app.data.get_item(Pollen.KEY)
        if pollen is None:
            return False

        self._app.data.clear_updated(Pollen.KEY)

        tree, grass = Pollen._parse_counts(pollen)
        if tree is None and grass is None:
            return False

        group = displayio.Group()

        if tree is not None:
            self._append_row(group, self._tree_icon, tree, _TREE_ICON_Y, _TREE_Y)

        if grass is not None:
            self._append_row(group, self._grass_icon, grass, _GRASS_ICON_Y, _GRASS_Y)

        mini_clock_width = mini_clock.bounding_box[2]
        mini_clock.x = self._app.canvas_width - mini_clock_width
        mini_clock.y = 2
        group.append(mini_clock)

        self._app.show_group(group)

        return True

    @staticmethod
    def _parse_counts(pollen):
        tree = grass = None

        if "tree" in pollen:
            try:
                tree = int(pollen["tree"])
            except (TypeError, ValueError):
                tree = None

        if "grass" in pollen:
            try:
                grass = int(pollen["grass"])
            except (TypeError, ValueError):
                grass = None

        return tree, grass

    @staticmethod
    def _make_icon(pixels, colors):
        height = len(pixels)
        width = max(len(row) for row in pixels)
        color_count = len(colors) + 1
        bitmap = displayio.Bitmap(width, height, color_count)
        palette = displayio.Palette(color_count)
        palette[0] = 0x000000
        palette.make_transparent(0)
        for index, color in enumerate(colors, start=1):
            palette[index] = color
        for y, row in enumerate(pixels):
            for x, pixel in enumerate(row):
                if pixel != ".":
                    bitmap[x, y] = int(pixel)
        return displayio.TileGrid(bitmap, pixel_shader=palette)

    @staticmethod
    def _append_row(group, icon, count, icon_y, text_y):
        row_icon = displayio.TileGrid(icon.bitmap, pixel_shader=icon.pixel_shader)
        row_icon.x = _ICON_X
        row_icon.y = icon_y
        group.append(row_icon)

        label = adafruit_display_text.label.Label(
            terminalio.FONT, color=_TEXT_COLOR, text=str(count)
        )
        label.x = _TEXT_X
        label.y = text_y
        group.append(label)

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
