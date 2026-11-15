# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Built-in modules must not collide over MQTT endpoints or names.

ModuleRegistry.register() refuses a duplicate NAME or endpoint and the caller
carries on, so a collision costs a module its MQTT subscriptions and its
screen while the sign otherwise boots normally — the kind of fault that shows
up as "that control does nothing" rather than as a crash.
"""

import pytest

from give_me_a_sign.aqi import AQI
from give_me_a_sign.clock import Clock
from give_me_a_sign.greet import Greet
from give_me_a_sign.image import Image
from give_me_a_sign.message import Message
from give_me_a_sign.module import ModuleStore
from give_me_a_sign.ota import OTA
from give_me_a_sign.pollen import Pollen
from give_me_a_sign.registry import ModuleRegistry
from give_me_a_sign.store_only import StoreOnly
from give_me_a_sign.tones import Tones
from give_me_a_sign.trimet import Trimet
from give_me_a_sign.uv import UV
from give_me_a_sign.weather import Weather

# Mirrors BUILTIN_MODULES in sign.py, which cannot be imported on CPython
# (it pulls in board, displayio, wifi and the rest of the hardware stack).
BUILTINS = (
    Clock,
    Tones,
    Greet,
    Message,
    Image,
    Weather,
    AQI,
    UV,
    Pollen,
    Trimet,
    StoreOnly,
    OTA,
)


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)

    def info(self, message):
        pass


class _Platform:  # pylint: disable=too-few-public-methods
    """Enough of Platform for the modules' constructors (Clock syncs NTP)."""

    wifi_is_connected = False

    def ntp_sync(self):
        return None


class _App:  # pylint: disable=too-few-public-methods
    def __init__(self):
        self.logger = _Logger()
        self.platform = _Platform()
        self.rtc = None


@pytest.fixture(name="app")
def _app(monkeypatch):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    return _App()


def test_every_builtin_registers(app):
    registry = ModuleRegistry(app)
    for module_cls in BUILTINS:
        assert registry.register(module_cls(app)), f"{module_cls.__name__} rejected"
    assert not app.logger.errors
    assert len(registry.modules()) == len(BUILTINS)


def test_ota_endpoints_are_reachable(app):
    registry = ModuleRegistry(app)
    for module_cls in BUILTINS:
        registry.register(module_cls(app))

    for endpoint in OTA.ENDPOINTS:
        assert registry.by_endpoint(endpoint) is registry.get("ota")


def test_no_duplicate_names_or_endpoints():
    names = [module_cls.NAME for module_cls in BUILTINS]
    assert len(names) == len(set(names))

    endpoints = [
        endpoint for module_cls in BUILTINS for endpoint in module_cls.ENDPOINTS
    ]
    assert len(endpoints) == len(set(endpoints))
