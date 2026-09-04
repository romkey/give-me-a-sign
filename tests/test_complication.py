# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for composed screen rendering."""

from types import SimpleNamespace

import displayio
import pytest

from give_me_a_sign.complication import Composer
from give_me_a_sign.module import ModuleStore, SignModule
from give_me_a_sign.registry import ModuleRegistry


class _Logger:
    def error(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass


class _App:
    def __init__(self):
        self.logger = _Logger()
        self.modules = ModuleRegistry(self)
        self._shown = None

    def show_group(self, group):
        self._shown = group


class _SlotModule(SignModule):
    NAME = "slot"
    ENDPOINTS = ("slot",)

    def __init__(self, app):
        super().__init__(app)
        self._complications = [
            __import__(
                "give_me_a_sign.complication", fromlist=["Complication"]
            ).Complication(
                "eighth",
                32,
                8,
                self._render,
            )
        ]

    def _render(self):
        return displayio.Group()

    def complications(self):
        return self._complications


@pytest.fixture
def composer(monkeypatch):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    app = _App()
    app.modules.register(_SlotModule(app))
    return Composer(app), app


def test_composer_places_complication(composer):
    comp, app = composer
    entry = {
        "type": "composed",
        "duration": 10,
        "complications": [{"ref": "slot.eighth", "x": 32, "y": 0}],
    }
    assert comp.show(entry) is True
    assert app._shown is not None
    assert app._shown[0].x == 32
    assert app._shown[0].y == 0


def test_composer_unknown_ref_skips(composer):
    comp, _ = composer
    entry = {
        "type": "composed",
        "duration": 10,
        "complications": [{"ref": "missing.eighth", "x": 0, "y": 0}],
    }
    assert comp.show(entry) is False
