# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Pytest configuration: CircuitPython stubs and shared fixtures."""

import sys
import types
from pathlib import Path

import pytest

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


@pytest.fixture(name="fake_dualbank")
def _fake_dualbank(monkeypatch):
    """Stand in for the dualbank module in both places that reach for it."""
    # imported here: give_me_a_sign is only importable once sys.path is set up
    # above. pylint: disable=import-outside-toplevel
    from give_me_a_sign import firmware_image, ota

    calls = types.SimpleNamespace(writes=[], switched=False)

    def flash(buffer, *, offset=0):
        calls.writes.append((offset, bytes(buffer)))

    def switch():
        calls.switched = True

    fake = types.SimpleNamespace(flash=flash, switch=switch)
    # ota.py checks for the module; firmware_image.py does the writing
    monkeypatch.setattr(ota, "dualbank", fake)
    monkeypatch.setattr(firmware_image, "dualbank", fake)
    return calls
