# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``adafruit_display_text.label`` stub for host-side unit tests."""

# Mirrors the real Label geometry closely enough for layout tests: y is not
# the top edge, it sits half the font ascent below it, and bounding_box[1]
# reports that as a negative offset. Measured from terminalio.FONT, whose
# glyph cell is 12 rows with the text starting 5 rows above y.
_ASCENT_OFFSET = 5
_CELL_HEIGHT = 12


class Label:
    def __init__(self, font, color=0xFFFFFF, text="", **kwargs):
        self.font = font
        self.color = color
        self.text = text
        self.x = kwargs.get("x", 0)
        self.y = kwargs.get("y", 0)
        width = max(1, len(text)) * 6
        self.bounding_box = [0, -_ASCENT_OFFSET, width, _CELL_HEIGHT]
