# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Pytest configuration: CircuitPython stubs and shared fixtures."""

import sys
import types
from pathlib import Path

_STUBS = Path(__file__).resolve().parent / "stubs"
_REPO = Path(__file__).resolve().parent.parent
_PKG = _REPO / "give_me_a_sign"

for _path in (_STUBS, _REPO):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

# Import submodules without executing give_me_a_sign/__init__.py (which pulls
# in the full sign application and every hardware dependency).
if "give_me_a_sign" not in sys.modules:
    _package = types.ModuleType("give_me_a_sign")
    _package.__path__ = [str(_PKG)]
    sys.modules["give_me_a_sign"] = _package
