# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT
import time
import sys
import microcontroller

from give_me_a_sign import GiveMeASign

"""
Example of how you might use GiveMeASign() module
"""

print("hello world")

app = GiveMeASign()
app.start()

# https://docs.python.org/3/library/exceptions.html
while True:
    try:
        app.loop()
    except Exception:  # pylint: disable=broad-exception-caught
        try:
            tb = sys.exception().__traceback__
            app.logger.error(tb)
            time.sleep(2)
        except Exception:  # pylint: disable=broad-exception-caught
            microcontroller.reset()
