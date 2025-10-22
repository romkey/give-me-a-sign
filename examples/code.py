# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT
import traceback
import board
import displayio
import rgbmatrix
import framebufferio
import microcontroller
import supervisor

from give_me_a_sign import GiveMeASign

"""
Example of how you might use GiveMeASign() module
"""

# board.DISPLAY.root_group = None

# comment this line out if you want to turn autoreload on
supervisor.runtime.autoreload = False

print("hello world")

displayio.release_displays()
matrix = rgbmatrix.RGBMatrix(
    width=64,
    height=32,
    bit_depth=2,
    rgb_pins=[
        board.MTX_R1,
        board.MTX_G1,
        board.MTX_B1,
        board.MTX_R2,
        board.MTX_G2,
        board.MTX_B2,
    ],
    addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
)
display = framebufferio.FramebufferDisplay(matrix, rotation=0)

app = GiveMeASign(display)
app.start()

while True:
    try:
        app.loop()
    except Exception as outer_exception:  # pylint: disable=broad-exception-caught
        try:
            print("General Exception 1", traceback.format_exception(outer_exception))
            app.logger.error(traceback.format_exception(outer_exception))
        except Exception as inner_exception:  # pylint: disable=broad-exception-caught
            print("General Exception 2", traceback.format_exception(inner_exception))
            microcontroller.reset()
