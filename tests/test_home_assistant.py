# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for Home Assistant MQTT autodiscovery configs."""

from give_me_a_sign.home_assistant import HomeAssistant


class _DummyMQTT:
    def __init__(self):
        self.published = []

    def publish(self, *args, **kwargs):
        self.published.append({"args": args, "kwargs": kwargs})


def _configs_by_topic(messages):
    return {message["topic"]: message["payload"] for message in messages}


def test_autodiscovery_includes_device_time_and_publish_data():
    base = "givemeasign/sign/aa_bb_cc_dd_ee_ff"
    ha = HomeAssistant("aa:bb:cc:dd:ee:ff", _DummyMQTT(), base)
    configs = _configs_by_topic(ha.create_autodiscovery_config())

    datetime_topic = (
        "homeassistant/datetime/givemeasign_aa_bb_cc_dd_ee_ff/device_time/config"
    )
    button_topic = (
        "homeassistant/button/givemeasign_aa_bb_cc_dd_ee_ff/publish_data/config"
    )

    assert datetime_topic in configs
    datetime_payload = configs[datetime_topic]
    assert datetime_payload["command_topic"] == f"{base}/time/set"
    assert datetime_payload["state_topic"] == f"{base}/time/state"
    assert datetime_payload["unique_id"] == "givemeasign_aa_bb_cc_dd_ee_ff_device_time"
    assert datetime_payload["entity_category"] == "config"
    assert datetime_payload["availability_topic"] == f"{base}/available"

    assert button_topic in configs
    button_payload = configs[button_topic]
    assert button_payload["command_topic"] == f"{base}/data/publish"
    assert button_payload["payload_press"] == "publish"
    assert button_payload["unique_id"] == "givemeasign_aa_bb_cc_dd_ee_ff_publish_data"
    assert button_payload["entity_category"] == "diagnostic"
    assert button_payload["availability_topic"] == f"{base}/available"


def test_autodiscovery_still_includes_reboot_and_display():
    base = "givemeasign/sign/aa_bb_cc_dd_ee_ff"
    ha = HomeAssistant("aa:bb:cc:dd:ee:ff", _DummyMQTT(), base)
    configs = _configs_by_topic(ha.create_autodiscovery_config())

    reboot = configs["homeassistant/button/givemeasign_aa_bb_cc_dd_ee_ff/reboot/config"]
    assert reboot["command_topic"] == f"{base}/reboot"
    assert reboot["payload_press"] == "reboot"

    display = configs[
        "homeassistant/switch/givemeasign_aa_bb_cc_dd_ee_ff/display/config"
    ]
    assert display["command_topic"] == f"{base}/display/set"
    assert display["state_topic"] == f"{base}/display/state"


def test_autodiscovery_uses_expected_sensor_metadata_and_notify_template():
    base = "givemeasign/sign/aa_bb_cc_dd_ee_ff"
    ha = HomeAssistant("aa:bb:cc:dd:ee:ff", _DummyMQTT(), base)
    configs = _configs_by_topic(ha.create_autodiscovery_config())

    free_memory = configs[
        "homeassistant/sensor/givemeasign_aa_bb_cc_dd_ee_ff/free_memory/config"
    ]
    assert free_memory["unit_of_measurement"] == "MiB"
    assert free_memory["state_class"] == "measurement"

    last_update = configs[
        "homeassistant/sensor/givemeasign_aa_bb_cc_dd_ee_ff/last_update/config"
    ]
    assert last_update["value_template"] == "{{ value_json.time_utc_iso }}"

    notify_message = configs[
        "homeassistant/notify/givemeasign_aa_bb_cc_dd_ee_ff/message/config"
    ]
    assert notify_message["command_template"] == "{{ value_json.message }}"


def test_publish_advertisements_uses_retain_and_qos_1():
    base = "givemeasign/sign/aa_bb_cc_dd_ee_ff"
    mqtt = _DummyMQTT()
    ha = HomeAssistant("aa:bb:cc:dd:ee:ff", mqtt, base)

    ha.publish_advertisements()

    assert mqtt.published
    assert all(call["kwargs"].get("retain") is True for call in mqtt.published)
    assert all(call["kwargs"].get("qos") == 1 for call in mqtt.published)
