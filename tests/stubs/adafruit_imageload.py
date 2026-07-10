# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``adafruit_imageload`` stub for host-side unit tests."""


def load(path, bitmap=None, palette=None):
    raise OSError(f"imageload stub: {path} not found")
