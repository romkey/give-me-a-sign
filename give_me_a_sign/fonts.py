# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/fonts - shared bitmap font loading
=================================================

* Author: John Romkey
"""

from adafruit_bitmap_font import bitmap_font

from ._paths import ASSETS_DIR

FULL = ASSETS_DIR + "/IBMPlexMono-Medium-24_jep.bdf"
SMALL = ASSETS_DIR + "/fonts/intelone-mono-font-family-regular-6.bdf"

_loaded = {}


def load(path):
    """
    Load a bitmap font, reusing an already-loaded font for the same path.

    Fonts are several KB each once their glyphs are cached, and the same few
    files are wanted by several modules, so on a memory-constrained board it
    matters that they are loaded once rather than per caller.
    """
    font = _loaded.get(path)
    if font is None:
        font = bitmap_font.load_font(path)
        _loaded[path] = font
    return font


def small():
    """
    The 6px font, the largest that fits an eighth slot.

    An eighth slot is 8 rows tall and ``displayio.Group`` does not clip its
    children, so a taller font paints over whatever is stacked beneath it.
    ``terminalio.FONT`` has a 12-row glyph cell and so cannot be used there.
    """
    return load(SMALL)


def full():
    """The 24px font used for the full-screen clock."""
    return load(FULL)
