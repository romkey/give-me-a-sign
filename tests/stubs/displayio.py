# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``displayio`` stub for host-side unit tests."""


class Group(list):
    def __init__(self, scale=1, x=0, y=0):
        super().__init__()
        self.scale = scale
        self.x = x
        self.y = y


class Bitmap:
    def __init__(self, width, height, colors):
        self.width = width
        self.height = height


class Palette:
    def __init__(self, count):
        self._colors = [0] * count

    def __setitem__(self, index, value):
        self._colors[index] = value


class TileGrid:
    def __init__(self, bitmap, pixel_shader, **kwargs):
        self.bitmap = bitmap
        self.pixel_shader = pixel_shader
        self.x = kwargs.get("x", 0)
        self.y = kwargs.get("y", 0)
