# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT
import gc
import time
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

# Throttle tight error loops (serial / USB); align with give_me_a_sign CP 10+ (traceback API).
_LOOP_ERR_SLEEP_S = 0.5
_OS_ERROR_BACKOFF_S = 1.0
_MEMORY_ERR_BACKOFF_S = 2.0


def _log_exception(prefix, err):
    """Requires CircuitPython 10+ / Python 3.10+ (single-argument format_exception)."""
    lines = traceback.format_exception(err)
    print(prefix)
    for line in lines:
        print(line, end="")
    try:
        app.logger.error("".join(lines))
    except Exception:  # pylint: disable=broad-exception-caught
        print("logger.error failed while reporting exception")


while True:
    try:
        app.loop()
    except MemoryError:
        print("MemoryError in app.loop(); gc.collect() and backing off")
        gc.collect()
        time.sleep(_MEMORY_ERR_BACKOFF_S)
    except OSError as outer_exception:
        try:
            _log_exception("OSError in app.loop():", outer_exception)
        except Exception as inner_exception:  # pylint: disable=broad-exception-caught
            print("Failed while formatting OSError traceback:", inner_exception)
            microcontroller.reset()
        time.sleep(_OS_ERROR_BACKOFF_S)
    except Exception as outer_exception:  # pylint: disable=broad-exception-caught
        try:
            _log_exception("Exception in app.loop():", outer_exception)
        except Exception as inner_exception:  # pylint: disable=broad-exception-caught
            print("Failed while formatting traceback:", inner_exception)
            microcontroller.reset()
        time.sleep(_LOOP_ERR_SLEEP_S)
