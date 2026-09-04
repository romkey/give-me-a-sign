# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``adafruit_display_text.label`` stub for host-side unit tests."""

# Real Label geometry, measured from the fonts this project ships: y is not
# the top edge, the text starts bounding_box[1] rows above it (half the font
# ascent, negative), and bounding_box[3] is the glyph cell height.
#
#   terminalio.FONT                    bounding_box = (0, -5, w, 12)
#   intelone-mono-6 (fonts.small())    bounding_box = (0, -2, w, 6)
#
# The 12-row terminalio cell is why it cannot be used in an 8-row eighth slot.
_METRICS = {
    "terminal_font": (-5, 12, 6),
}
_SMALL = (-2, 6, 5)


def _metrics(font):
    return _METRICS.get(font, _SMALL)


class Label:
    def __init__(self, font, color=0xFFFFFF, text="", **kwargs):
        self.font = font
        self.color = color
        self.text = text
        self.x = kwargs.get("x", 0)
        self.y = kwargs.get("y", 0)
        top, height, char_width = _metrics(font)
        width = max(1, len(text)) * char_width
        self.bounding_box = [0, top, width, height]
