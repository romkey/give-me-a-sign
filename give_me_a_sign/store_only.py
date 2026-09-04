# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/store_only - endpoints with no display
=====================================================

* Author: John Romkey
"""

from .module import SignModule


class StoreOnly(SignModule):
    """
    Stores MQTT data for endpoints that have no display module.
    """

    NAME = "store_only"
    ENDPOINTS = ("debug", "lunar")

    def show(self) -> bool:
        return False
