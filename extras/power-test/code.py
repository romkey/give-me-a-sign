# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/extras/power-test - application module for LED Matrix display
====================================================

* Author: John Romkey
"""

from power import Power

p = Power()
while True:
    p.loop()
