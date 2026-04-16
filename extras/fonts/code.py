# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
Simple program to display examples of font files found on the device
"""

import os
import gc

import supervisor

import board
import displayio
import digitalio

from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.scrolling_label import ScrollingLabel
from adafruit_debouncer import Button
from adafruit_matrixportal.matrix import Matrix

from give_me_a_sign._paths import ASSETS_DIR

# comment this line out if you want to turn autoreload on
supervisor.runtime.autoreload = False

print("hello world")

displayio.release_displays()
matrix = Matrix()
display = matrix.display
display.root_group = None

pin = digitalio.DigitalInOut(board.BUTTON_UP)
pin.direction = digitalio.Direction.INPUT
pin.pull = digitalio.Pull.UP
up_button = Button(pin)

pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
pin.direction = digitalio.Direction.INPUT
pin.pull = digitalio.Pull.UP
down_button = Button(pin)

TEXT = "0123456789:-_.AMPMampm"
DRAW = True
INDEX = 0

print(os.listdir(ASSETS_DIR + "/fonts"))

files = [file for file in os.listdir(ASSETS_DIR + "/fonts") if file[0] != "."]
# Alternate filter:
# files = [file for file in os.listdir(ASSETS_DIR + "/fonts") if file[:-4] == ".bdf"]

print("files", files)
files.sort()

if len(files) == 0:
    print("No fonts found")
    while True:
        pass

while True:
    up_button.update()
    down_button.update()

    if up_button.pressed:
        DRAW = True
        INDEX += 1
        if INDEX == len(files):
            INDEX = 0

    if down_button.pressed:
        DRAW = True
        INDEX -= 1
        if INDEX == -1:
            INDEX = len(files) - 1

    if DRAW:
        print(INDEX, files[INDEX])

        font = bitmap_font.load_font(ASSETS_DIR + "/fonts/" + files[INDEX])
        label = ScrollingLabel(
            font, text=TEXT, max_characters=len(TEXT), animate_time=0.5
        )
        label.y = 10
        display.root_group = label
        DRAW = False
        gc.collect()

    label.update()
