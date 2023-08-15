# SPDX-FileCopyrightText: 2023 John Romkey
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
draw = True
index = 0

print(os.listdir("/assets/fonts"))

files = [file for file in os.listdir("/assets/fonts") if file[0] != "."]
# files = [file for file in os.listdir("/assets/fonts") if file[1] != "." and file[:-4] == ".bdf"]

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
        draw = True
        index += 1
        if index == len(files):
            index = 0

    if down_button.pressed:
        draw = True
        index -= 1
        if index == -1:
            index = len(files) - 1

    if draw:
        print(index, files[index])

        font = bitmap_font.load_font(f"/assets/fonts/{files[index]}")
        label = ScrollingLabel(
            font, text=TEXT, max_characters=len(TEXT), animate_time=0.5
        )
        label.y = 10
        display.root_group = label
        draw = False
        gc.collect()

    label.update()
