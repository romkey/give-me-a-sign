# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``storage`` stub for host-side unit tests."""

remount_calls = []


def remount(path, readonly):
    remount_calls.append((path, readonly))


def reset():
    remount_calls.clear()
