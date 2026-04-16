# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/mqtt - MQTT support for Give Me A Sign
====================================================

* Author: John Romkey
"""
import os
import json
import time
import gc
import sys
import board
import microcontroller

import adafruit_minimqtt.adafruit_minimqtt as MQTT

from .aqi import AQI
from .clock import Clock
from .greet import Greet
from .image import Image
from .message import Message
from .pollen import Pollen
from .tones import Tones
from .trimet import Trimet
from .uv import UV
from .weather import Weather
from .home_assistant import HomeAssistant

MQTT_RETRY_MIN_S = 5
MQTT_RETRY_MAX_S = 120
MQTT_FAILURES_BEFORE_RESET = 20


class SignMQTT:  # pylint: disable=too-many-instance-attributes
    """
    SignMQTT subscribes to an MQTT broker in order to receive data on various topics
    that map to modules that display the data.
    """

    STORE_ENDPOINTS = [
        AQI.KEY,
        "debug",
        "forecast",
        Greet.KEY,
        Image.KEY,
        "lunar",
        Message.KEY,
        Pollen.KEY,
        Clock.KEY_SOLAR,
        Clock.KEY_TIMEZONE,
        Tones.KEY,
        Trimet.KEY,
        UV.KEY,
        Weather.KEY,
    ]

    def __init__(self, app, platform):
        self._app = app
        self._platform = platform
        self._id = self._platform.wifi_mac_address.replace(":", "_")
        self._next_diagnostic_time = 0
        self._topic_prefix = os.getenv("MQTT_TOPIC_PREFIX") or "givemeasign"
        self._ha_sign_base = f"givemeasign/sign/{self._id}"
        self._display_state_topic = f"{self._ha_sign_base}/display/state"
        self._display_command_topic = f"{self._ha_sign_base}/display/set"

        self._mqtt = None
        self._home_assistant = None
        self._mqtt_failures = 0
        self._mqtt_next_retry_at = 0.0
        self._mqtt_backoff_s = MQTT_RETRY_MIN_S

        if self._platform.wifi_is_connected:
            print("WiFi connected!")
        else:
            print("WiFi NOT connected!")

        self._build_mqtt_client()
        try:
            self._mqtt_connect_and_subscribe()
        except Exception as error:  # pylint: disable=broad-exception-caught
            print("MQTT initial connect failed:", error)
            self._on_mqtt_failure()

    def _build_mqtt_client(self):
        socket = self._platform.get_socket()

        if not self._platform.native:
            MQTT.set_socket(socket, self._platform.esp)

            self._mqtt = MQTT.MQTT(
                broker=os.getenv("MQTT_BROKER"),
                port=os.getenv("MQTT_PORT") or 1888,
                is_ssl=os.getenv("MQTT_SSL") or False,
                client_id=os.getenv("MQTT_CLIENTID"),
                username=os.getenv("MQTT_USERNAME"),
                password=os.getenv("MQTT_PASSWORD"),
            )
        else:
            self._mqtt = MQTT.MQTT(
                broker=os.getenv("MQTT_BROKER"),
                port=os.getenv("MQTT_PORT") or 1888,
                is_ssl=os.getenv("MQTT_SSL") or False,
                client_id=os.getenv("MQTT_CLIENTID"),
                username=os.getenv("MQTT_USERNAME"),
                password=os.getenv("MQTT_PASSWORD"),
                socket_pool=socket,
            )

        print("MQTT Connect")
        self._mqtt.onconnect = lambda: print("onconnect")
        self._mqtt.will_set(f"givemeasign/sign/{self._id}/available", "offline", True)

    def _subscribe_all_topics(self):
        for endpoint in self.STORE_ENDPOINTS:
            topic = f"{self._topic_prefix}/all/module/{endpoint}"
            self._mqtt.subscribe(topic)
            self._mqtt.add_topic_callback(
                topic,
                lambda client, topic, message, key=endpoint: self.store_data(
                    key, message
                ),
            )

        topic = f"{self._topic_prefix}/{self._id}/reboot"
        self._mqtt.subscribe(topic)
        self._mqtt.add_topic_callback(
            topic,
            lambda client, topic, message, key=None: microcontroller.reset(),
        )

        self._mqtt.subscribe(self._display_command_topic)
        self._mqtt.add_topic_callback(
            self._display_command_topic, self._on_display_command
        )

    def _mqtt_connect_and_subscribe(self):
        self._mqtt.connect()
        self._subscribe_all_topics()
        print("MQTT Connected")
        if self._home_assistant is None:
            self._home_assistant = HomeAssistant(
                self._app.platform.wifi_mac_address, self._mqtt
            )
        else:
            self._home_assistant.set_mqtt_client(self._mqtt)
        self.publish_display_state()
        self._mqtt_failures = 0
        self._mqtt_backoff_s = MQTT_RETRY_MIN_S
        self._mqtt_next_retry_at = 0.0

    def _on_mqtt_failure(self):
        now = time.monotonic()
        self._mqtt_next_retry_at = now + self._mqtt_backoff_s
        self._mqtt_backoff_s = min(self._mqtt_backoff_s * 2, MQTT_RETRY_MAX_S)
        self._mqtt_failures += 1
        if self._mqtt_failures >= MQTT_FAILURES_BEFORE_RESET:
            print("MQTT: too many consecutive failures, resetting MCU")
            microcontroller.reset()

    def _maybe_retry_mqtt(self):
        if time.monotonic() < self._mqtt_next_retry_at:
            return
        try:
            if self._mqtt is None:
                self._build_mqtt_client()
            self._mqtt_connect_and_subscribe()
        except Exception as error:  # pylint: disable=broad-exception-caught
            print("MQTT reconnect failed:", error)
            self._on_mqtt_failure()

    def _rebuild_mqtt_after_wifi(self):
        try:
            if self._mqtt is not None:
                self._mqtt.disconnect()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self._mqtt = None
        self._build_mqtt_client()
        try:
            self._mqtt_connect_and_subscribe()
        except Exception as error:  # pylint: disable=broad-exception-caught
            print("MQTT rebuild after WiFi failed:", error)
            self._on_mqtt_failure()

    def is_connected_to_broker(self) -> bool:
        """Return whether the MQTT client is currently connected."""
        if self._mqtt is None:
            return False
        try:
            return self._mqtt.is_connected()
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    @staticmethod
    def _decode_mqtt_payload(message):
        if isinstance(message, memoryview):
            message = bytes(message)
        if isinstance(message, bytes):
            return message.decode()
        return str(message)

    def _on_display_command(self, _client, _topic, message):
        """Home Assistant switch: ON = show content, OFF = blank the matrix."""
        text = self._decode_mqtt_payload(message).strip().upper()
        if text == "ON":
            self._app.display_enabled = True
        elif text == "OFF":
            self._app.display_enabled = False
        else:
            return
        self.publish_display_state()

    def publish_display_state(self):
        """Publish retained display switch state for Home Assistant."""
        if not self.is_connected_to_broker():
            return
        payload = "ON" if self._app.display_enabled else "OFF"
        self._mqtt.publish(self._display_state_topic, payload, retain=True, qos=1)

    def store_data(self, key, message):
        """
        Generic endpoint used to store a received message using the specified key. Attempts to
        parse the message as JSON and stores it on success. Logs an error on failure.
        """
        print(f"mqtt store_data! {key}", message)
        try:
            data = json.loads(message)
        except ValueError:
            self._app.logger.error(
                f"server:store_data({key}) store_data failed: {message}"
            )
            return

        self._app.data.set_item(key, data)

        self._app.logger.info(f"server:store_data({key}) got JSON")
        self._app.logger.info(data)

    def _publish_diagnostics(self):
        """
        Periodically publish diagnostic information about the state of the sign
        """
        if not self._app.platform.wifi_is_connected:
            print("MQTT - disconnected, not publishing diagnostics")
            return

        flash = os.statvfs("/")
        flash_size = flash[0] * flash[2]
        flash_free = flash[0] * flash[3]

        info = {
            "uptime": time.monotonic_ns() / 1e9,
            "time_utc": time.time(),
            "timezone_offset": self._app.clock.timezone_offset,
            "free_memory": gc.mem_free(),  # pylint: disable=no-member
            "flash_free": flash_free,
            "flash_size": flash_size,
            "rtc": "ESP32"
            if self._app.rtc.__class__.__name__ == "RTC"
            else self._app.rtc.__class__.__name__,
            "wifi_ssid": self._app.platform.wifi_ssid,
            "wifi_bssid": self._app.platform.wifi_bssid,
            "wifi_rssi": self._app.platform.wifi_rssi,
            "mac_address": self._app.platform.wifi_mac_address,
            "ipv4address": str(self._app.platform.wifi_ip_address),
            "python_version": sys.version,
            "circuitpython_version": ".".join([str(i) for i in sys.implementation[1]]),
            "platform": sys.platform,
            "board": board.board_id,
            "display_height": self._app.display.height,
            "display_width": self._app.display.width,
        }

        self._mqtt.publish(f"givemeasign/sign/{self._id}/diagnostics", json.dumps(info))

    def loop(self):
        """
        Perform housekeeping tasks in the loop
        Makes sure we're still connected to the broker,
        and gives the protocol engine a chance to run.
        """
        if (
            hasattr(self._platform, "wifi_just_restored")
            and self._platform.wifi_just_restored()
        ):
            print("WiFi restored, rebuilding MQTT client")
            self._rebuild_mqtt_after_wifi()

        if not self._platform.wifi_is_connected:
            return

        if self._mqtt is None or not self.is_connected_to_broker():
            self._maybe_retry_mqtt()
            return

        if self._home_assistant is None:
            self._home_assistant = HomeAssistant(
                self._app.platform.wifi_mac_address, self._mqtt
            )

        try:
            self._home_assistant.loop()

            if time.monotonic_ns() > self._next_diagnostic_time:
                print("MQTT publishing diagnostics")
                self._publish_diagnostics()
                self._next_diagnostic_time = time.monotonic_ns() + 60e9

            self._mqtt.loop(1)
        except BrokenPipeError as error:
            print("MQTT BrokenPipeError", error)
            try:
                if self._mqtt is not None:
                    self._mqtt.disconnect()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._mqtt = None
            self._on_mqtt_failure()
        except (OSError, RuntimeError) as error:
            print("MQTT loop error:", error)
            self._on_mqtt_failure()
