# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``supervisor`` stub for host-side unit tests."""

import os


def get_setting(key, default):
    value = os.getenv(key)
    if value is None:
        return default
    if isinstance(default, bool):
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default
    return value
