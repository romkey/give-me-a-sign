# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``adafruit_debouncer`` stub for host-side unit tests."""


class Button:
    def __init__(self, pin):
        self.pin = pin
        self.long_press = False
        self.value = True

    def update(self):
        pass
