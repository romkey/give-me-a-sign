# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/platform - networking for native-WiFi LED matrix boards
====================================================

* Author: John Romkey
"""

import os
import time
import wifi
import socketpool

import adafruit_ntp

from .mqtt import SignMQTT

WIFI_RETRY_MIN_S = 5
WIFI_RETRY_MAX_S = 90
# bound each connect attempt so a missing AP can't stall the loop for long
WIFI_CONNECT_TIMEOUT_S = 10


class Platform:
    """
    Platform functions for boards with native WiFi (e.g. Matrix Portal S3).

    Manages WiFi, NTP, and MQTT.
    """

    def __init__(self, app):
        self._app = app
        self._ntp = None
        self._mqtt = None
        self._socket_pool = None
        self._wifi_next_retry_at = 0
        self._wifi_backoff_s = WIFI_RETRY_MIN_S
        self._wifi_restored_flag = False

    def _refresh_socket_pool_and_ntp(self):
        self._socket_pool = socketpool.SocketPool(wifi.radio)
        # short socket timeout: a failed sync stalls the display loop for
        # its duration (default would be 10 seconds)
        self._ntp = adafruit_ntp.NTP(self._socket_pool, tz_offset=0, socket_timeout=5)

    def wifi_connect(self) -> None:
        """
        Attempt to connect to wifi

        Just return if already connected
        """
        if not wifi.radio.connected:
            ssid = os.getenv("wifi_ssid")
            password = os.getenv("wifi_password")

            if ssid is None or password is None:
                print("wifi_ssid or wifi_password not set in secrets.toml")
                return

            # Catch broadly: if any connect error escaped, the caller's loop
            # would retry with no backoff and the blocking connect calls
            # would effectively freeze the display.
            try:
                wifi.radio.connect(ssid, password, timeout=WIFI_CONNECT_TIMEOUT_S)
            except (OSError, RuntimeError) as error:
                print("wifi failure:", error)
                return

        self._refresh_socket_pool_and_ntp()
        self._wifi_backoff_s = WIFI_RETRY_MIN_S
        self._wifi_next_retry_at = 0

    def _try_wifi_reconnect(self) -> None:
        # monotonic_ns doesn't lose precision over long uptimes like monotonic does
        now = time.monotonic_ns()
        if now < self._wifi_next_retry_at:
            return

        ssid = os.getenv("wifi_ssid")
        password = os.getenv("wifi_password")
        if ssid is None or password is None:
            return

        print("WiFi reconnect attempt")
        try:
            wifi.radio.connect(ssid, password, timeout=WIFI_CONNECT_TIMEOUT_S)
        except (OSError, RuntimeError) as error:
            print("wifi reconnect failed:", error)
            self._wifi_next_retry_at = now + int(self._wifi_backoff_s * 1e9)
            self._wifi_backoff_s = min(self._wifi_backoff_s * 2, WIFI_RETRY_MAX_S)
            return

        self._refresh_socket_pool_and_ntp()
        self._wifi_backoff_s = WIFI_RETRY_MIN_S
        self._wifi_next_retry_at = 0
        self._wifi_restored_flag = True
        print("WiFi reconnected")

    def wifi_just_restored(self) -> bool:
        """One-shot for MQTT to rebuild its client with a fresh socket pool."""
        if self._wifi_restored_flag:
            self._wifi_restored_flag = False
            return True
        return False

    @property
    def wifi_is_connected(self) -> bool:
        """
        True is WiFi is currently connected
        """
        return wifi.radio.connected

    @property
    def wifi_ssid(self) -> str:
        """
        Return the SSID of the current WiFi connection
        """
        return wifi.radio.ap_info.ssid

    @property
    def wifi_rssi(self) -> int:
        """
        Return the RSSI (signal strength) of the current WiFi connection
        """
        return wifi.radio.ap_info.rssi

    @property
    def wifi_bssid(self) -> str:
        """
        Return the BSSID of the current WiFi connection
        (the access point's MAC address)
        """
        return ":".join("%02x" % b for b in wifi.radio.ap_info.bssid)

    @property
    def wifi_mac_address(self) -> str:
        """
        Return the WiFi MAC address
        """
        return ":".join("%02x" % b for b in wifi.radio.mac_address)

    @property
    def wifi_ip_address(self):
        """
        Return the current IP address if connected to WiFi
        """
        return wifi.radio.ipv4_address

    def get_socket(self):
        """
        Return a socket pool tied to the current WiFi session.
        """
        if self._socket_pool is not None and self.wifi_is_connected:
            return self._socket_pool
        return socketpool.SocketPool(wifi.radio)

    def ntp_sync(self) -> int:
        """
        Get the current time in UTC from NTP
        """
        if self._ntp is None or not self.wifi_is_connected:
            return None

        try:
            return self._ntp.datetime
        except (OSError, RuntimeError, ArithmeticError):
            return None

    def start_mqtt(self) -> None:
        """Start the MQTT client."""
        self._mqtt = SignMQTT(self._app, self)

    @property
    def mqtt_is_connected(self) -> bool:
        """Return whether the MQTT client is connected to its broker."""
        if self._mqtt is None:
            return False
        return self._mqtt.is_connected_to_broker()

    def loop(self) -> None:
        """
        Perform any repetitive tasks necessary

        Each subsystem is isolated so one failure can't starve the display
        state machine (an exception escaping here aborts the whole app loop
        iteration, every iteration, freezing the sign).
        """
        if not self.wifi_is_connected:
            self._try_wifi_reconnect()

        if self._mqtt:
            self._mqtt.loop()
