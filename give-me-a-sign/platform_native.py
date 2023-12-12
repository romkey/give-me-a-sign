# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/platform_native - clock module for LED Matrix display
====================================================

* Author: John Romkey
"""

import os
import wifi
import socketpool

import adafruit_ntp

from native_http_server import AppServer
from mqtt import SignMQTT


class Platform:
    """
    Platform functions for native networking (built into the microcontroller,
    like an ESP32).

    Includes functions to manage wifi, use NTP and start the web server
    """

    def __init__(self, app):
        self._app = app
        self._ntp = None
        self._server = None
        self._mqtt = None

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

            try:
                wifi.radio.connect(ssid, password)
            except ConnectionError:
                print("wifi failure")
                return

        pool = socketpool.SocketPool(wifi.radio)
        self._ntp = adafruit_ntp.NTP(pool, tz_offset=0)

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

    def get_socket(self):  # pylint: disable=no-self-use
        """
        Return a socket
        """
        return socketpool.SocketPool(wifi.radio)

    @property
    def native(self) -> bool:
        """
        Return true if this platform is native
        """
        return True

    def ntp_sync(self) -> int:
        """
        Get the current time in UTC from NTP
        """
        if self._ntp is not None:
            return self._ntp.datetime

        return None

    def start_servers(self) -> None:
        """
        Start the web application server
        """
        self._mqtt = SignMQTT(self._app, self)
        self._server = AppServer(self._app)
        self._server.start()

    @property
    def server(self):
        """
        Return the web application server object
        """
        return self._server

    def loop(self) -> None:
        """
        Perform any repetitive tasks necessary
        """
        if self._server:
            self._server.loop()

        if self._mqtt:
            self._mqtt.loop()
