# SPDX-FileCopyrightText: 2023-2025 John Romkey
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

from aqi import AQI
from clock import Clock
from greet import Greet
from image import Image
from message import Message
from pollen import Pollen
from tones import Tones
from trimet import Trimet
from uv import UV
from weather import Weather
from home_assistant import HomeAssistant


class SignMQTT:
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

        if self._platform.wifi_is_connected:
            print("WiFi connected!")
        else:
            print("WiFi NOT connected!")

        socket = self._platform.get_socket()

        if not platform.native:
            MQTT.set_socket(socket, platform.esp)

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

        # must be called *before* connect
        self._mqtt.will_set(f"givemeasign/sign/{self._id}/available", "offline", True)

        self._mqtt.connect()
        topic_prefix = os.getenv("MQTT_TOPIC_PREFIX") or "givemeasign"
        for endpoint in self.STORE_ENDPOINTS:
            topic = f"{topic_prefix}/all/module/{endpoint}"
            self._mqtt.subscribe(topic)
            self._mqtt.add_topic_callback(
                topic,
                lambda client, topic, message, key=endpoint: self.store_data(
                    key, message
                ),
            )

        topic = f"{topic_prefix}/{self._id}/reboot"
        self._mqtt.subscribe(topic)
        self._mqtt.add_topic_callback(
            topic, lambda client, topic, message, key=endpoint: microcontroller.reset()
        )

        print("MQTT Connected")
        self._home_assistant = HomeAssistant(
            self._app.platform.wifi_mac_address, self._mqtt
        )

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
        if not self._mqtt.is_connected():
            print("MQTT reconnecting")
            self._mqtt.reconnect(True)

        try:
            self._home_assistant.loop()

            if time.monotonic_ns() > self._next_diagnostic_time:
                print("MQTT publishing diagnostics")
                self._publish_diagnostics()
                self._next_diagnostic_time = time.monotonic_ns() + 60e9

            self._mqtt.loop(1)
        except BrokenPipeError:
            print("MQTT BrokenPipeError")
            try:
                print("MQTT try reconnect")
                self._mqtt.reconnect(True)
            except Exception as error:  # pylint: disable=broad-exception-caught
                print("Caught unexpected exception", error)
                print("Giving up and restarting")
                microcontroller.reset()
