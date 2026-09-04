# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for MQTT payload dispatch in ``give_me_a_sign.mqtt.SignMQTT``."""

import pytest

from give_me_a_sign.greet import Greet
from give_me_a_sign.message import Message
from give_me_a_sign.mqtt import SignMQTT
from give_me_a_sign.registry import ModuleRegistry
from give_me_a_sign.weather import Weather


class _Logger:
    def __init__(self):
        self.errors = []
        self.infos = []

    def error(self, message, *args):
        self.errors.append(message)

    def info(self, message, *args):
        self.infos.append(message)


class _App:
    def __init__(self):
        self.logger = _Logger()
        self.display_enabled = True
        self.modules = ModuleRegistry(self)
        self.modules.register(Weather(self))
        self.modules.register(Message(self))
        self.modules.register(Greet(self))


@pytest.fixture
def sign_mqtt(monkeypatch):
    monkeypatch.setattr(
        "give_me_a_sign.module.ModuleStore._restore", lambda self: False
    )
    app = _App()
    mqtt = SignMQTT.__new__(SignMQTT)
    mqtt._app = app
    return mqtt


def test_decode_mqtt_payload():
    assert SignMQTT._decode_mqtt_payload(b"hello") == "hello"
    assert SignMQTT._decode_mqtt_payload(memoryview(b"world")) == "world"
    assert SignMQTT._decode_mqtt_payload("plain") == "plain"


def test_dispatch_valid_json(sign_mqtt):
    sign_mqtt._dispatch("weather", '{"current": {"temperature": 70}}')
    weather = sign_mqtt._app.modules.get("weather")
    assert weather.store.get_item("weather") == {"current": {"temperature": 70}}


def test_dispatch_plain_text_message(sign_mqtt):
    sign_mqtt._dispatch("message", "hello there")
    message = sign_mqtt._app.modules.get("message")
    assert message.store.get_item("message") == {"text": "hello there"}


def test_dispatch_plain_text_greet(sign_mqtt):
    sign_mqtt._dispatch("greet", "Jane D.")
    greet = sign_mqtt._app.modules.get("greet")
    assert greet.store.get_item("greet") == {"person": "Jane D."}


def test_dispatch_json_string_message(sign_mqtt):
    sign_mqtt._dispatch("message", '"hello"')
    message = sign_mqtt._app.modules.get("message")
    assert message.store.get_item("message") == {"text": "hello"}


def test_dispatch_message_dict_with_message_key(sign_mqtt):
    sign_mqtt._dispatch("message", '{"message": "notify text"}')
    message = sign_mqtt._app.modules.get("message")
    assert message.store.get_item("message") == {"text": "notify text"}


def test_dispatch_json_string_greet(sign_mqtt):
    sign_mqtt._dispatch("greet", '"Jane D."')
    greet = sign_mqtt._app.modules.get("greet")
    assert greet.store.get_item("greet") == {"person": "Jane D."}


def test_dispatch_invalid_json_other_endpoint(sign_mqtt):
    sign_mqtt._dispatch("weather", "not json")
    weather = sign_mqtt._app.modules.get("weather")
    assert weather.store.get_item("weather") is None
    assert sign_mqtt._app.logger.errors
