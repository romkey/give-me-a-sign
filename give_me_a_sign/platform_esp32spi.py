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
import board
from digitalio import DigitalInOut
import microcontroller

from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_socket as socket

from .ntp import AppNTP

# from esp32spi_http_server import AppServer
# from native_http_server import AppServer
from .mqtt import SignMQTT

WIFI_RETRY_MIN_S = 5
WIFI_RETRY_MAX_S = 90
WIFI_FAILURES_BEFORE_RESET = 12


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
        self._wifi_next_retry_at = 0.0
        self._wifi_backoff_s = WIFI_RETRY_MIN_S
        self._wifi_failures = 0
        self._wifi_restored_flag = False

        spi = board.SPI()
        esp32_cs = DigitalInOut(board.ESP_CS)
        esp32_ready = DigitalInOut(board.ESP_BUSY)
        esp32_reset = DigitalInOut(board.ESP_RESET)
        self.esp = adafruit_esp32spi.ESP_SPIcontrol(
            spi, esp32_cs, esp32_ready, esp32_reset
        )

        print(f"ESP AirLift version {self.esp.firmware_version.decode()}")

    def wifi_connect(self) -> None:
        """
        Attempt to connect to wifi

        Just return if already connected
        """
        if not self.esp.is_connected:
            ssid = os.getenv("wifi_ssid")
            password = os.getenv("wifi_password")

            if ssid is None or password is None:
                print("wifi_ssid or wifi_password not set in secrets.toml")
                return

            try:
                self.esp.connect({"ssid": ssid, "password": password})
            except ConnectionError:
                print("wifi failure (will retry in background)")
                print("scanning...")
                for access_point in self.esp.scan_networks():
                    print(
                        f'\t{access_point["ssid"].decode()}\t\tRSSI: {access_point["rssi"]}'
                    )
                self._wifi_failures += 1
                self._wifi_next_retry_at = time.monotonic() + self._wifi_backoff_s
                self._wifi_backoff_s = min(self._wifi_backoff_s * 2, WIFI_RETRY_MAX_S)
                return

            print(
                "MAC address ",
                ":".join(
                    "%02x" % b
                    for b in self.esp.MAC_address_actual  # pylint: disable=consider-using-f-string,line-too-long
                ),
            )

        self._ntp = AppNTP(self.esp)
        self._wifi_backoff_s = WIFI_RETRY_MIN_S
        self._wifi_next_retry_at = 0.0
        self._wifi_failures = 0

    def _try_wifi_reconnect(self) -> None:
        now = time.monotonic()
        if now < self._wifi_next_retry_at:
            return

        ssid = os.getenv("wifi_ssid")
        password = os.getenv("wifi_password")
        if ssid is None or password is None:
            return

        print("WiFi reconnect attempt (ESP32SPI)")
        try:
            self.esp.connect({"ssid": ssid, "password": password})
        except ConnectionError as error:
            print("wifi reconnect failed:", error)
            self._wifi_failures += 1
            self._wifi_next_retry_at = now + self._wifi_backoff_s
            self._wifi_backoff_s = min(self._wifi_backoff_s * 2, WIFI_RETRY_MAX_S)
            if self._wifi_failures >= WIFI_FAILURES_BEFORE_RESET:
                print("WiFi: too many failures, resetting MCU")
                time.sleep(2)
                microcontroller.reset()
            return

        self._ntp = AppNTP(self.esp)
        self._wifi_backoff_s = WIFI_RETRY_MIN_S
        self._wifi_next_retry_at = 0.0
        self._wifi_failures = 0
        self._wifi_restored_flag = True
        print("WiFi reconnected (ESP32SPI)")

    def wifi_just_restored(self) -> bool:
        """One-shot so MQTT can reconnect cleanly after ESP32SPI WiFi returns."""
        if self._wifi_restored_flag:
            self._wifi_restored_flag = False
            return True
        return False

    @property
    def wifi_is_connected(self) -> bool:
        """
        Return whether wifi is currently connected or not
        """
        return self.esp.is_connected

    @property
    def wifi_ssid(self) -> str:
        """
        Return the SSID of the current WiFi connection
        """
        return self.esp.ssid.decode()

    @property
    def wifi_rssi(self) -> int:
        """
        Return the RSSI (signal strength) of the current WiFi connection
        """
        return self.esp.rssi

    @property
    def wifi_bssid(self) -> str:
        """
        Return the BSSID of the current WiFi connection
        (the access point's MAC address)
        """
        return ":".join("%02x" % b for b in self.esp.bssid)

    @property
    def wifi_mac_address(self) -> str:
        """
        Return the WiFi MAC address
        """
        return ":".join("%02x" % b for b in self.esp.MAC_address_actual)

    @property
    def wifi_ip_address(self):
        """
        Return the current IP address if connected to WiFi
        """
        return self.esp.ip_address

    def get_socket(self):  # pylint: disable=no-self-use
        """
        Return a socket or socketpool
        """
        #        return self.esp.get_socket()
        return socket

    @property
    def native(self) -> bool:
        """
        Return true if this platform is native
        """
        return False

    def ntp_sync(self) -> int:
        """
        Get the current time in UTC from NTP
        """
        if self._ntp is not None:
            return self._ntp.update()

        return None

    def start_servers(self) -> None:
        """
        Start the MQTT and/or web application servers
        """
        self._mqtt = SignMQTT(self._app, self)

    #        self._server = AppServer(self._app)
    #        self._server.start()

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
        """
        if not self.wifi_is_connected:
            self._try_wifi_reconnect()

        if self._server:
            self._server.loop()

        if self._mqtt:
            self._mqtt.loop()
