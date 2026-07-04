# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT
import gc
import os
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

Display geometry is configurable in settings.toml for larger displays
built from multiples of the standard 64x32 panel:

    MATRIX_WIDTH = 128         # total pixels across (chained panels)
    MATRIX_PANEL_HEIGHT = 32   # rows per panel: 32, or 64 (needs ADDR E jumper)
    MATRIX_TILE = 2            # rows of panels stacked vertically
    MATRIX_SERPENTINE = true   # alternate panel rows rotated 180 degrees
    MATRIX_BIT_DEPTH = 2       # more depth = more colors, more RAM/CPU

On CircuitPython older than 10.2, settings.toml values must be strings or
ints, so use MATRIX_SERPENTINE = 1 (or "true") instead of a bare boolean.

The example above drives a 128x64 display made of four 64x32 panels,
two across and two down. Content is laid out on a 64x32 canvas and
integer-scaled to fit, so no other configuration is needed.
"""

# board.DISPLAY.root_group = None

# comment this line out if you want to turn autoreload on
supervisor.runtime.autoreload = False

print("hello world")


def _get_setting(key, default):
    """
    Read a typed value from settings.toml.

    Uses supervisor.get_setting() where available (CircuitPython 10.2+),
    otherwise falls back to os.getenv() and coerces the value to the type
    of the default.
    """
    getter = getattr(supervisor, "get_setting", None)
    if getter is not None:
        return getter(key, default)

    value = os.getenv(key)
    if value is None:
        return default
    if isinstance(default, bool):
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default
    return value


MATRIX_WIDTH = _get_setting("MATRIX_WIDTH", 64)
MATRIX_PANEL_HEIGHT = _get_setting("MATRIX_PANEL_HEIGHT", 32)
MATRIX_TILE = _get_setting("MATRIX_TILE", 1)
MATRIX_SERPENTINE = _get_setting("MATRIX_SERPENTINE", True)
MATRIX_BIT_DEPTH = _get_setting("MATRIX_BIT_DEPTH", 2)

if MATRIX_WIDTH % 64 != 0 or MATRIX_WIDTH < 64:
    raise ValueError("MATRIX_WIDTH must be a positive multiple of 64")
if MATRIX_PANEL_HEIGHT not in (32, 64):
    raise ValueError("MATRIX_PANEL_HEIGHT must be 32 or 64")
if MATRIX_TILE < 1:
    raise ValueError("MATRIX_TILE must be at least 1")

# 64-row panels need a fifth address line (close the ADDR E jumper on the
# panel and use a board that provides it, e.g. MatrixPortal S3)
addr_pins = [board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD]
if MATRIX_PANEL_HEIGHT == 64:
    if not hasattr(board, "MTX_ADDRE"):
        raise ValueError("64-row panels need MTX_ADDRE, which this board lacks")
    addr_pins.append(board.MTX_ADDRE)

displayio.release_displays()
matrix = rgbmatrix.RGBMatrix(
    width=MATRIX_WIDTH,
    height=MATRIX_PANEL_HEIGHT * MATRIX_TILE,
    bit_depth=MATRIX_BIT_DEPTH,
    rgb_pins=[
        board.MTX_R1,
        board.MTX_G1,
        board.MTX_B1,
        board.MTX_R2,
        board.MTX_G2,
        board.MTX_B2,
    ],
    addr_pins=addr_pins,
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
    tile=MATRIX_TILE,
    serpentine=MATRIX_SERPENTINE,
)
display = framebufferio.FramebufferDisplay(matrix, rotation=0)

# If startup fails (transient WiFi/hardware trouble), reset and try again
# rather than leaving a headless sign dead until someone power-cycles it.
# A persistent config error becomes a slow boot loop, visible on serial.
try:
    app = GiveMeASign(display)
    app.start()
except Exception as startup_error:  # pylint: disable=broad-exception-caught
    print("Fatal error during startup:", startup_error)
    traceback.print_exception(startup_error)
    time.sleep(30)
    microcontroller.reset()

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
