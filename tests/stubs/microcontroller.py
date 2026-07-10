# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``microcontroller`` stub for host-side unit tests."""


def reset():
    raise RuntimeError("microcontroller.reset() called")
