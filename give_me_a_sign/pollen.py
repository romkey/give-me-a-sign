# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/pollen - pollen count module for LED Matrix display
==================================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import displayio
import terminalio

from .clock import Clock
from .complication import EIGHTH, FULL, HALF_WIDE, Complication, place_top
from .module import SignModule

_BROWN = 0xA52A2A
_GREEN = 0x00FF00
_TEXT_COLOR = 0x800080
_ICON_X = 0
_TEXT_X = 10
_TREE_Y = 8
_GRASS_Y = 24
_TREE_ICON_Y = 0
_GRASS_ICON_Y = 16

_HALF_TEXT_Y = HALF_WIDE[1] // 2
_HALF_COLUMN_X = HALF_WIDE[0] // 2

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


class Pollen(SignModule):
    """
    Manages the display of Pollen Count on the sign.
    """

    NAME = "pollen"
    KEY = "pollen"
    ENDPOINTS = (KEY,)
    STALE_SECONDS = 60 * 60

    def __init__(self, app):
        super().__init__(app)
        self._tree_icon = Pollen._make_icon(_TREE_PIXELS, (_BROWN, _GREEN))
        self._grass_icon = Pollen._make_icon(_GRASS_PIXELS, (_GREEN,))
        self._complications = None

    def _counts(self):
        pollen = self.store.get_item(Pollen.KEY)
        if pollen is None:
            return None, None
        return Pollen._parse_counts(pollen)

    def show(self) -> bool:
        self.store.clear_updated(Pollen.KEY)
        group = self._build_group("full")
        if group is None:
            return False
        self._app.show_group(group)
        return True

    def _build_group(self, layout):
        tree, grass = self._counts()
        if tree is None and grass is None:
            return None

        group = displayio.Group()
        if layout == "full":
            if tree is not None:
                self._append_row(group, self._tree_icon, tree, _TREE_ICON_Y, _TREE_Y)
            if grass is not None:
                self._append_row(
                    group, self._grass_icon, grass, _GRASS_ICON_Y, _GRASS_Y
                )
            Clock.append_mini_clock(self._app, group)
        elif layout == "half":
            # Two side-by-side columns in a 64x16 slot, not two stacked rows.
            if tree is not None:
                self._append_row(group, self._tree_icon, tree, 0, _HALF_TEXT_Y)
            if grass is not None:
                self._append_row(
                    group,
                    self._grass_icon,
                    grass,
                    0,
                    _HALF_TEXT_Y,
                    x_offset=_HALF_COLUMN_X,
                )
        elif layout == "tree":
            if tree is None:
                return None
            self._append_row(group, self._tree_icon, tree, 0, None)
        elif layout == "grass":
            if grass is None:
                return None
            self._append_row(group, self._grass_icon, grass, 0, None)
        return group

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
    def _append_row(  # pylint: disable=too-many-arguments
        group, icon, count, icon_y, text_y, x_offset=0
    ):
        """
        Draw one icon-and-count row.

        *text_y* is the label's y as displayio understands it. Pass None to
        top-align the count instead, for slots too short to place it by eye.
        """
        row_icon = displayio.TileGrid(icon.bitmap, pixel_shader=icon.pixel_shader)
        row_icon.x = _ICON_X + x_offset
        row_icon.y = icon_y
        group.append(row_icon)
        label = adafruit_display_text.label.Label(
            terminalio.FONT, color=_TEXT_COLOR, text=str(count)
        )
        label.x = _TEXT_X + x_offset
        if text_y is None:
            place_top(label)
        else:
            label.y = text_y
        group.append(label)

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication(
                    "full", FULL[0], FULL[1], lambda: self._build_group("full")
                ),
                Complication(
                    "half",
                    HALF_WIDE[0],
                    HALF_WIDE[1],
                    lambda: self._build_group("half"),
                ),
                Complication(
                    "tree", EIGHTH[0], EIGHTH[1], lambda: self._build_group("tree")
                ),
                Complication(
                    "grass", EIGHTH[0], EIGHTH[1], lambda: self._build_group("grass")
                ),
            ]
        return self._complications
