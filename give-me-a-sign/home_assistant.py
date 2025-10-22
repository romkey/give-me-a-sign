# SPDX-FileCopyrightText: 2025 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/give-me-a-sign - application module for LED Matrix display
====================================================

* Author: John Romkey
"""

import json
import time
import os
import give_me_a_sign


class HomeAssistant:
    """
    Home Assistant Autodiscovery module
    Publishes messages to MQTT that inform Home Assistant of functionality in GiveMeASign
    """

    def __init__(self, mac_address, mqtt_client):
        """Initialize Home Assistant MQTT autodiscovery manager

        Args:
            mac_address (str): Device MAC address (e.g., "34:85:18:b1:ef:28")
            mqtt_client: MQTT client object with publish() method
        """
        self._name = "GiveMeASign - " + os.getenv("SIGN_NAME", mac_address)
        self._mac_address = mac_address
        self._mqtt_client = mqtt_client
        mac_clean = mac_address.replace(":", "_")
        self._device_id = f"givemeasign_{mac_clean}"
        self._base_topic = f"givemeasign/sign/{mac_clean}"
        self._availability_topic = f"{self._base_topic}/available"
        self._last_advertisement_time = 0
        self._advertisement_interval = 3600  # 1 hour in seconds

    def create_autodiscovery_config(self):  # pylint: disable=too-many-locals
        """Generate Home Assistant MQTT autodiscovery configuration"""

        device_info = {
            "identifiers": [self._device_id],
            "name": self._name,
            "model": "Adafruit MatrixPortal S3",
            "manufacturer": "Espressif",
            "sw_version": give_me_a_sign.__version__,
            "connections": [["mac", self._mac_address]],
        }

        sensors = {
            "python_version": {
                "name": "Python Version",
                "value_template": "{{ value_json.python_version }}",
                "icon": "mdi:language-python",
            },
            "free_memory": {
                "name": "Free Memory",
                "value_template": "{{ (value_json.free_memory / 1024 / 1024) | round(2) }}",
                "unit_of_measurement": "MB",
                "device_class": "data_size",
                "icon": "mdi:memory",
            },
            "flash_free": {
                "name": "Flash Free",
                "value_template": "{{ (value_json.flash_free / 1024 / 1024) | round(2) }}",
                "unit_of_measurement": "MB",
                "device_class": "data_size",
                "icon": "mdi:harddisk",
            },
            "flash_size": {
                "name": "Flash Size",
                "value_template": "{{ (value_json.flash_size / 1024 / 1024) | round(2) }}",
                "unit_of_measurement": "MB",
                "device_class": "data_size",
                "icon": "mdi:harddisk",
            },
            "last_update": {
                "name": "Last Update",
                "value_template": "{{ value_json.time_utc }}",
                "device_class": "timestamp",
                "icon": "mdi:clock",
            },
            "timezone_offset": {
                "name": "Timezone Offset",
                "value_template": "{{ (value_json.timezone_offset / 3600) | round(1) }}",
                "unit_of_measurement": "hours",
                "icon": "mdi:clock-time-eight",
            },
            "time_utc": {
                "name": "Current Timezone UTC",
                "value_template": "{{ value_json.time_utc }}",
                "unit_of_measurement": "seconds",
                "icon": "mdi:clock",
            },
        }

        diagnostics = {
            "board": {
                "name": "Device Board",
                "value_template": "{{ value_json.board }}",
                "icon": "mdi:developer-board",
            },
            "circuitpython_version": {
                "name": "CircuitPython Version",
                "value_template": "{{ value_json.circuitpython_version }}",
                "icon": "mdi:information",
            },
            "wifi_rssi": {
                "name": "WiFi RSSI",
                "value_template": "{{ value_json.wifi_rssi }}",
                "unit_of_measurement": "dBm",
                "device_class": "signal_strength",
                "icon": "mdi:wifi",
            },
            "wifi_ssid": {
                "name": "WiFi SSID",
                "value_template": "{{ value_json.wifi_ssid }}",
                "icon": "mdi:wifi",
            },
            "wifi_bssid": {
                "name": "WiFi BSSID",
                "value_template": "{{ value_json.wifi_bssid }}",
                "icon": "mdi:wifi",
            },
            "ip_address": {
                "name": "IP Address",
                "value_template": "{{ value_json.ipv4address }}",
                "icon": "mdi:ip-network",
            },
            "display_resolution": {
                "name": "Display Resolution",
                "value_template": "{{ value_json.display_width }}x{{ value_json.display_height }}",
                "icon": "mdi:monitor",
            },
            "uptime": {
                "name": "Uptime",
                "value_template": "{{ (value_json.uptime / 1000) | int }}",
                "unit_of_measurement": "s",
                "device_class": "duration",
                "icon": "mdi:clock",
            },
            "rtc_status": {
                "name": "RTC",
                "value_template": "{{ value_json.rtc }}",
                "icon": "mdi:clock-outline",
            },
        }

        text_inputs = {
            "greet": {
                "name": "Greeting Text",
                "command_topic": f"{self._base_topic}/module/greet",
                "icon": "mdi:hand-wave",
            },
            "message": {
                "name": "Message Text",
                "command_topic": f"{self._base_topic}/module/message",
                "icon": "mdi:message-text",
            },
        }

        buttons = {
            "reboot": {
                "name": "Reboot Device",
                "command_topic": f"{self._base_topic}/reboot",
                "payload_press": "reboot",
                "icon": "mdi:restart",
            }
        }

        autodiscovery_messages = []

        for sensor_key, sensor_config in sensors.items():
            topic = f"homeassistant/sensor/{self._device_id}/{sensor_key}/config"

            payload = {
                "name": sensor_config["name"],
                "state_topic": f"{self._base_topic}/diagnostics",
                "value_template": sensor_config["value_template"],
                "icon": sensor_config["icon"],
                "unique_id": f"{self._device_id}_{sensor_key}",
                "availability_topic": self._availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": device_info
                if sensor_key == "python_version"
                else {"identifiers": [self._device_id]},
            }

            if "unit_of_measurement" in sensor_config:
                payload["unit_of_measurement"] = sensor_config["unit_of_measurement"]
            if "device_class" in sensor_config:
                payload["device_class"] = sensor_config["device_class"]

            autodiscovery_messages.append({"topic": topic, "payload": payload})

        for diagnostic_key, diagnostic_config in diagnostics.items():
            topic = f"homeassistant/sensor/{self._device_id}/{diagnostic_key}/config"

            payload = {
                "name": diagnostic_config["name"],
                "state_topic": f"{self._base_topic}/diagnostics",
                "value_template": diagnostic_config["value_template"],
                "icon": diagnostic_config["icon"],
                "unique_id": f"{self._device_id}_{diagnostic_key}",
                "entity_category": "diagnostic",
                "availability_topic": self._availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": {"identifiers": [self._device_id]},
            }

            if "unit_of_measurement" in diagnostic_config:
                payload["unit_of_measurement"] = diagnostic_config[
                    "unit_of_measurement"
                ]
            if "device_class" in diagnostic_config:
                payload["device_class"] = diagnostic_config["device_class"]

            autodiscovery_messages.append({"topic": topic, "payload": payload})

        for text_key, text_config in text_inputs.items():
            topic = f"homeassistant/text/{self._device_id}/{text_key}/config"
            topic_notify = f"homeassistant/notify/{self._device_id}/{text_key}/config"

            payload = {
                "name": text_config["name"],
                "command_topic": text_config["command_topic"],
                "icon": text_config["icon"],
                "unique_id": f"{self._device_id}_{text_key}",
                "availability_topic": self._availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": {"identifiers": [self._device_id]},
            }

            autodiscovery_messages.append({"topic": topic, "payload": payload})
            autodiscovery_messages.append({"topic": topic_notify, "payload": payload})

        for button_key, button_config in buttons.items():
            topic = f"homeassistant/button/{self._device_id}/{button_key}/config"

            payload = {
                "name": button_config["name"],
                "command_topic": button_config["command_topic"],
                "payload_press": button_config["payload_press"],
                "icon": button_config["icon"],
                "unique_id": f"{self._device_id}_{button_key}",
                "availability_topic": self._availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": {"identifiers": [self._device_id]},
            }

            autodiscovery_messages.append({"topic": topic, "payload": payload})

        return autodiscovery_messages

    def publish_advertisements(self):
        """Publish all autodiscovery advertisements to Home Assistant"""
        print("Publishing Home Assistant autodiscovery advertisements...")

        advertisements = self.create_autodiscovery_config()

        for message in advertisements:
            topic = message["topic"]
            payload = json.dumps(message["payload"])

            # Publish with retain=True so Home Assistant can discover after restart
            self._mqtt_client.publish(topic, payload, retain=True)

        print(f"Published {len(advertisements)} autodiscovery messages")

    def publish_online_status(self):
        """Publish 'online' status to availability topic"""
        self._mqtt_client.publish(
            self._availability_topic, "online", retain=True, qos=1
        )
        print("Published online status to availability topic")

    def loop(self):
        """Main loop - call this regularly from your main program loop"""
        current_time = time.time()

        # Check if it's time to publish advertisements (once per hour)
        if current_time - self._last_advertisement_time >= self._advertisement_interval:
            self.publish_advertisements()
            self.publish_online_status()
            self._last_advertisement_time = current_time

    def setup_mqtt_will(self):
        """Configure MQTT Last Will and Testament for offline detection
        Call this before connecting to MQTT broker"""
        return {
            "topic": self._availability_topic,
            "payload": "offline",
            "retain": True,
            "qos": 1,
        }
