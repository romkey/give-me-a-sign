# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT
import time
import traceback
import board
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

app = GiveMeASign()
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
