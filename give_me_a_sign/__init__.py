# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""CircuitPython library package for the Give Me A Sign LED matrix sign."""

from ._version import __repo__, __version__
from .sign import GiveMeASign

__all__ = ["GiveMeASign", "__version__", "__repo__"]
