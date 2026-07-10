# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for SignMQTT time payload parsing and time/set handling."""

import json
import time
from types import SimpleNamespace

import pytest

from give_me_a_sign.data import Data
from give_me_a_sign.mqtt import SignMQTT


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message, *args):
        self.errors.append(message)

    def info(self, message, *args):
        pass


class _FakeRTC:
    def __init__(self):
        self.datetime = None


class _RecordingMQTT:
    def __init__(self):
        self.published = []
        self._connected = True

    def is_connected(self):
        return self._connected

    def publish(self, topic, payload, retain=False, qos=0):
        self.published.append(
            {"topic": topic, "payload": payload, "retain": retain, "qos": qos}
        )


@pytest.fixture
def sign_mqtt(monkeypatch):
    monkeypatch.setattr(Data, "_restore", lambda self: False)
    mqtt = SignMQTT.__new__(SignMQTT)
    mqtt._app = SimpleNamespace(
        data=Data(),
        logger=_Logger(),
        rtc=_FakeRTC(),
        display_enabled=True,
    )
    mqtt._mqtt = _RecordingMQTT()
    mqtt._ha_sign_base = "givemeasign/sign/aa_bb_cc_dd_ee_ff"
    mqtt._time_state_topic = f"{mqtt._ha_sign_base}/time/state"
    mqtt._data_state_topic = f"{mqtt._ha_sign_base}/data/state"
    return mqtt


def test_parse_iso8601_plain():
    epoch = SignMQTT._parse_iso8601_utc("2026-07-10T12:30:45")
    assert epoch == SignMQTT._parse_iso8601_utc("2026-07-10T12:30:45+00:00")
    assert SignMQTT._epoch_to_iso_utc(epoch).startswith("2026-07-10T12:30:45")


def test_parse_iso8601_z_and_offset():
    base = SignMQTT._parse_iso8601_utc("2026-07-10T12:00:00Z")
    assert SignMQTT._parse_iso8601_utc("2026-07-10T12:00:00+00:00") == base
    # +01:00 means the wall clock is one hour ahead of UTC
    assert SignMQTT._parse_iso8601_utc("2026-07-10T13:00:00+01:00") == base
    assert SignMQTT._parse_iso8601_utc("2026-07-10T05:00:00-07:00") == base


def test_parse_iso8601_fractional_and_space():
    base = SignMQTT._parse_iso8601_utc("2026-07-10T12:00:00")
    assert SignMQTT._parse_iso8601_utc("2026-07-10T12:00:00.123456Z") == base
    assert SignMQTT._parse_iso8601_utc("2026-07-10 12:00:00") == base


def test_parse_iso8601_rejects_garbage():
    assert SignMQTT._parse_iso8601_utc("") is None
    assert SignMQTT._parse_iso8601_utc("not-a-date") is None
    assert SignMQTT._parse_iso8601_utc("2026-07-10") is None


def test_epoch_roundtrip_iso():
    epoch = 1_720_000_000
    iso = SignMQTT._epoch_to_iso_utc(epoch)
    assert SignMQTT._parse_iso8601_utc(iso) == epoch


def test_parse_time_payload_bare_epoch(sign_mqtt):
    assert sign_mqtt._parse_time_payload("1700000000") == 1_700_000_000
    assert sign_mqtt._parse_time_payload(b"1700000000") == 1_700_000_000
    assert sign_mqtt._parse_time_payload("1700000000.9") == 1_700_000_000


def test_parse_time_payload_json_epoch(sign_mqtt):
    assert sign_mqtt._parse_time_payload('{"epoch": 1700000000}') == 1_700_000_000
    assert sign_mqtt._parse_time_payload("1700000000") == 1_700_000_000
    assert sign_mqtt._parse_time_payload("1.7e9") == 1_700_000_000


def test_parse_time_payload_iso_string(sign_mqtt):
    epoch = sign_mqtt._parse_time_payload("2026-07-10T12:00:00+00:00")
    assert epoch == SignMQTT._parse_iso8601_utc("2026-07-10T12:00:00Z")
    # JSON-encoded ISO string
    assert sign_mqtt._parse_time_payload('"2026-07-10T12:00:00Z"') == epoch


def test_parse_time_payload_rejects_bad(sign_mqtt):
    assert sign_mqtt._parse_time_payload("") is None
    assert sign_mqtt._parse_time_payload("   ") is None
    assert sign_mqtt._parse_time_payload("not-a-time") is None
    assert sign_mqtt._parse_time_payload('{"epoch": "nope"}') is None
    assert sign_mqtt._parse_time_payload("{}") is None


def test_on_time_command_sets_rtc_and_publishes(sign_mqtt):
    epoch = 1_700_000_000
    sign_mqtt._on_time_command(None, "topic", str(epoch))

    assert sign_mqtt._app.rtc.datetime == time.localtime(epoch)
    assert len(sign_mqtt._mqtt.published) == 1
    published = sign_mqtt._mqtt.published[0]
    assert published["topic"] == sign_mqtt._time_state_topic
    assert published["payload"] == SignMQTT._epoch_to_iso_utc(epoch)
    assert published["retain"] is True
    assert published["qos"] == 1
    assert not sign_mqtt._app.logger.errors


def test_on_time_command_iso_payload(sign_mqtt):
    iso = "2026-07-10T12:00:00+00:00"
    epoch = SignMQTT._parse_iso8601_utc(iso)
    sign_mqtt._on_time_command(None, "topic", iso)

    assert sign_mqtt._app.rtc.datetime == time.localtime(epoch)
    assert sign_mqtt._mqtt.published[0]["payload"] == SignMQTT._epoch_to_iso_utc(epoch)


def test_on_time_command_bad_payload(sign_mqtt):
    sign_mqtt._on_time_command(None, "topic", "garbage")

    assert sign_mqtt._app.rtc.datetime is None
    assert sign_mqtt._mqtt.published == []
    assert sign_mqtt._app.logger.errors


def test_on_time_command_rtc_oserror(sign_mqtt):
    class _FailingRTC:
        @property
        def datetime(self):
            return None

        @datetime.setter
        def datetime(self, _value):
            raise OSError("i2c fail")

    sign_mqtt._app.rtc = _FailingRTC()
    sign_mqtt._on_time_command(None, "topic", "1700000000")

    assert sign_mqtt._mqtt.published == []


def test_publish_data_store(sign_mqtt):
    sign_mqtt._app.data.set_item("aqi", {"aqi": 58})
    sign_mqtt._app.data.set_item("message", {"text": "hi"})

    sign_mqtt.publish_data_store()

    assert len(sign_mqtt._mqtt.published) == 1
    published = sign_mqtt._mqtt.published[0]
    assert published["topic"] == sign_mqtt._data_state_topic
    assert published["retain"] is True
    assert published["qos"] == 1

    payload = json.loads(published["payload"])
    assert payload["aqi"]["data"] == {"aqi": 58}
    assert payload["message"]["data"] == {"text": "hi"}
    assert "last_updated" in payload["aqi"]
    assert "updated" in payload["aqi"]


def test_on_publish_data_command(sign_mqtt):
    sign_mqtt._app.data.set_item("uv", {"index": 5})
    sign_mqtt._on_publish_data_command(None, "topic", "publish")

    assert len(sign_mqtt._mqtt.published) == 1
    assert sign_mqtt._mqtt.published[0]["topic"] == sign_mqtt._data_state_topic


def test_publish_data_store_skips_when_disconnected(sign_mqtt):
    sign_mqtt._mqtt._connected = False
    sign_mqtt._app.data.set_item("aqi", {"aqi": 1})
    sign_mqtt.publish_data_store()
    assert sign_mqtt._mqtt.published == []
