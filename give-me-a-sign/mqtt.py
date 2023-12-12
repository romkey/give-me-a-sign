# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/mqtt - MQTT support for Give Me A Sign
====================================================

* Author: John Romkey
"""
import os
import json

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
        print("MQTT Connected")

    def store_data(self, key, message):
        """
        Generic endpoint used to store a received message using the specified key. Attempts to
        parse the message as JSON and stores it on success. Logs an error on failure.
        """
        print(f"mqtt store_data! {key} - {message}")
        try:
            data = json.loads(message)
        except ValueError:
            self._app.logger.error(
                f"server:store_data({key}) store_data failed: {message}"
            )
            return

        self._app.data.set_item(key, data)

        self._app.logger.info(f"server:store_data({key}) got JSON: {data}")

    def loop(self):
        """
        Perform housekeeping tasks in the loop
        Makes sure we're still connected to the broker,
        and gives the protocol engine a chance to run.
        """
        if not self._mqtt.is_connected():
            self._mqtt.reconnect(True)

        self._mqtt.loop()
