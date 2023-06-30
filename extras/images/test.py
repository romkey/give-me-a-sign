# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: CC0-1.0
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/extras/images/test.py - application module for LED Matrix display
====================================================

* Author: John Romkey
"""

import os
import time

import displayio

from adafruit_matrixportal.matrix import Matrix
import adafruit_imageload

displayio.release_displays()

matrix = Matrix()
display = matrix.display

for filename in os.listdir("test"):
    print(f"displaying {filename}")
    bitmap, palette = adafruit_imageload.load(
        "test/" + filename, bitmap=displayio.Bitmap, palette=displayio.Palette
    )
    tile_group = displayio.TileGrid(bitmap, pixel_shader=palette)
    group = displayio.Group()
    group.append(tile_group)
    display.show(group)

    time.sleep(15)

print("done")
while True:
    pass
