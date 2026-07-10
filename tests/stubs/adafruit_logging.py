# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``adafruit_logging`` stub for host-side unit tests."""

INFO = 20
ERROR = 40


class StreamHandler:
    pass


class Logger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(("info", message))

    def error(self, message, *args):
        self.messages.append(("error", message))

    def addHandler(self, handler):
        pass

    def setLevel(self, level):
        pass


def getLogger(name):
    return Logger()
