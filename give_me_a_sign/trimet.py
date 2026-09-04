# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/trimet - Trimet public transit module for LED Matrix display
===========================================================================

* Author: John Romkey
"""

from .module import SignModule


class Trimet(SignModule):
    """
    Stores Trimet transit data. Display is not yet implemented.
    """

    NAME = "trimet"
    KEY = "trimet"
    ENDPOINTS = (KEY,)

    def show(self) -> bool:
        return False
