# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for MQTT payload handling in ``give_me_a_sign.mqtt.SignMQTT``."""

import pytest

from give_me_a_sign.data import Data
from give_me_a_sign.mqtt import SignMQTT


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
        self.data = Data()
        self.logger = _Logger()
        self.display_enabled = True


@pytest.fixture
def sign_mqtt(monkeypatch):
    monkeypatch.setattr(Data, "_restore", lambda self: False)
    app = _App()
    mqtt = SignMQTT.__new__(SignMQTT)
    mqtt._app = app
    return mqtt


def test_decode_mqtt_payload():
    assert SignMQTT._decode_mqtt_payload(b"hello") == "hello"
    assert SignMQTT._decode_mqtt_payload(memoryview(b"world")) == "world"
    assert SignMQTT._decode_mqtt_payload("plain") == "plain"


def test_store_valid_json(sign_mqtt):
    sign_mqtt.store_data("weather", '{"current": {"temperature": 70}}')
    assert sign_mqtt._app.data.get_item("weather") == {"current": {"temperature": 70}}


def test_store_plain_text_message(sign_mqtt):
    sign_mqtt.store_data("message", "hello there")
    assert sign_mqtt._app.data.get_item("message") == {"text": "hello there"}


def test_store_plain_text_greet(sign_mqtt):
    sign_mqtt.store_data("greet", "Jane D.")
    assert sign_mqtt._app.data.get_item("greet") == {"person": "Jane D."}


def test_store_json_string_message(sign_mqtt):
    sign_mqtt.store_data("message", '"hello"')
    assert sign_mqtt._app.data.get_item("message") == {"text": "hello"}


def test_store_message_dict_with_message_key(sign_mqtt):
    sign_mqtt.store_data("message", '{"message": "notify text"}')
    assert sign_mqtt._app.data.get_item("message") == {"text": "notify text"}


def test_store_json_string_greet(sign_mqtt):
    sign_mqtt.store_data("greet", '"Jane D."')
    assert sign_mqtt._app.data.get_item("greet") == {"person": "Jane D."}


def test_store_invalid_json_other_endpoint(sign_mqtt):
    sign_mqtt.store_data("weather", "not json")
    assert sign_mqtt._app.data.get_item("weather") is None
    assert sign_mqtt._app.logger.errors
