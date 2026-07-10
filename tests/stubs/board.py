# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``board`` stub for host-side unit tests."""

board_id = "test_board"
BUTTON_UP = "BUTTON_UP"
BUTTON_DOWN = "BUTTON_DOWN"
A4 = "A4"


class _I2C:
    def try_lock(self):
        return False

    def unlock(self):
        pass


def I2C():  # pylint: disable=invalid-name
    return _I2C()
