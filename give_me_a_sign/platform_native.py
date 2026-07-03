# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/platform_native - clock module for LED Matrix display
====================================================

* Author: John Romkey
"""

import os
import time
import wifi
import socketpool

import adafruit_ntp

from .native_http_server import AppServer
from .mqtt import SignMQTT

WIFI_RETRY_MIN_S = 5
WIFI_RETRY_MAX_S = 90
# bound each connect attempt so a missing AP can't stall the loop for long
WIFI_CONNECT_TIMEOUT_S = 10
SERVER_RETRY_INTERVAL_NS = 10 * 1_000_000_000


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
        self._server_wanted = False
        self._server_next_retry_at = 0
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
        # the old server's sockets died with the connection; loop() rebuilds it
        self._drop_server()
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
        if self._ntp is None or not self.wifi_is_connected:
            return None

        try:
            return self._ntp.datetime
        except (OSError, RuntimeError, ArithmeticError):
            return None

    def start_servers(self) -> None:
        """
        Start MQTT and the web application server. If WiFi isn't up yet
        the HTTP server start is deferred to loop() rather than letting a
        failure here kill the whole app at boot.
        """
        self._mqtt = SignMQTT(self._app, self)
        self._server_wanted = True
        self._ensure_server()

    def _drop_server(self) -> None:
        """Close the HTTP server's listening socket so a rebuild can rebind."""
        if self._server is None:
            return
        try:
            self._server.stop()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self._server = None

    def _ensure_server(self) -> None:
        """Start (or restart) the HTTP server once WiFi is available."""
        if not self._server_wanted or self._server is not None:
            return
        if not self.wifi_is_connected:
            return
        if time.monotonic_ns() < self._server_next_retry_at:
            return

        try:
            server = AppServer(self._app)
            server.start()
        except (OSError, RuntimeError) as error:
            print("HTTP server start failed, will retry:", error)
            self._server_next_retry_at = time.monotonic_ns() + SERVER_RETRY_INTERVAL_NS
            return

        self._server = server

    @property
    def server(self):
        """
        Return the web application server object
        """
        return self._server

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

        self._ensure_server()

        if self._server:
            try:
                self._server.loop()
            except (OSError, RuntimeError) as error:
                print("HTTP server poll failed, restarting server:", error)
                self._drop_server()

        if self._mqtt:
            self._mqtt.loop()
