# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``adafruit_minimqtt`` stub for host-side unit tests."""


class MQTT:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._connected = False
        self._callbacks = {}

    def will_set(self, *args, **kwargs):
        pass

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected

    def subscribe(self, topic):
        pass

    def add_topic_callback(self, topic, callback):
        self._callbacks[topic] = callback

    def publish(self, topic, payload, retain=False, qos=0):
        pass

    def loop(self, timeout=1):
        pass
