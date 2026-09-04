# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for ModuleRegistry."""

import sys
import types

import pytest

from give_me_a_sign.module import ModuleStore, SignModule
from give_me_a_sign.registry import ModuleRegistry, discover_lib_modules


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message, *_args, **_kwargs):
        self.errors.append(message)

    def info(self, *_args, **_kwargs):
        pass


class _App:
    def __init__(self):
        self.logger = _Logger()


class _Alpha(SignModule):
    NAME = "alpha"
    ENDPOINTS = ("alpha",)


class _Beta(SignModule):
    NAME = "beta"
    ENDPOINTS = ("beta",)


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    return ModuleRegistry(_App())


def test_register_and_lookup(registry):
    alpha = _Alpha(registry._app)
    assert registry.register(alpha) is True
    assert registry.get("alpha") is alpha
    assert registry.by_endpoint("alpha") is alpha


def test_duplicate_name_rejected(registry):
    assert registry.register(_Alpha(registry._app)) is True
    assert registry.register(_Alpha(registry._app)) is False


def test_load_external(registry, monkeypatch):
    external = types.ModuleType("gmas_demo")
    external.MODULES = [_Beta]

    monkeypatch.setitem(sys.modules, "gmas_demo", external)
    registry.load_external(["gmas_demo"])
    assert registry.get("beta") is not None


def test_discover_lib_modules(monkeypatch, tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "gmas_foo.py").write_text("# demo", encoding="utf-8")
    (lib / "other.py").write_text("# skip", encoding="utf-8")

    monkeypatch.setattr(
        "give_me_a_sign.registry.os.listdir", lambda _path: ["gmas_foo.py", "other.py"]
    )
    assert discover_lib_modules() == ["gmas_foo"]
