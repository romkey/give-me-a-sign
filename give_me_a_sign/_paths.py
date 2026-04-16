# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Directory paths for files shipped inside the ``give_me_a_sign`` package."""

_PKG_DIR = __file__.rsplit("/", 1)[0]

# Bundled bitmaps, fonts, etc. live next to the .py files (e.g. ``/lib/give_me_a_sign/assets``).
ASSETS_DIR = _PKG_DIR + "/assets"
