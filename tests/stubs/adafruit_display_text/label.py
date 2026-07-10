# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``adafruit_display_text.label`` stub for host-side unit tests."""


class Label:
    def __init__(self, font, color=0xFFFFFF, text="", **kwargs):
        self.font = font
        self.color = color
        self.text = text
        self.x = kwargs.get("x", 0)
        self.y = kwargs.get("y", 0)
        width = max(1, len(text)) * 6
        self.bounding_box = [0, 0, width, 8]
