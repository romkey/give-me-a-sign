# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/extras/power-test - application module for LED Matrix display
====================================================

* Author: John Romkey
"""

import time
import gc
import board
import displayio
import digitalio
import microcontroller

from adafruit_esp32spi import adafruit_esp32spi
from adafruit_matrixportal.matrix import Matrix

from server import Server

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


class Power:
    """
    Sets up the display and ESP32 and web server, then loops and
    lets the web server do the work.
    """

    def __init__(self):
        displayio.release_displays()

        self.matrix = Matrix()
        self.display = self.matrix.display

        self._setup_esp()
        self._connect_wifi()

        print(f"IP address {self.esp.pretty_ip(self.esp.ip_address)}")
        self.server = Server(self)  # pylint: disable=attribute-defined-outside-init
        self.server.start()

    def _setup_esp(self):
        """
        Initialize the ESP32 wifi coprocessor
        """
        spi = board.SPI()
        esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
        esp32_ready = digitalio.DigitalInOut(board.ESP_BUSY)
        esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
        self.esp = adafruit_esp32spi.ESP_SPIcontrol(
            spi, esp32_cs, esp32_ready, esp32_reset
        )

        print(f"ESP AirLift version {self.esp.firmware_version.decode()}")

    def _connect_wifi(self):
        """
        Connect to wifi!

        This seems to mysteriously fail often.
        """
        try:
            self.esp.connect(secrets)
        except ConnectionError:
            print("wifi failure")
            print("scanning...")
            for access_point in self.esp.scan_networks():
                print(
                    f'\t{access_point["ssid"].decode()}\t\tRSSI: {access_point["rssi"]}'
                )

            time.sleep(5)
            microcontroller.reset()

        print(
            "MAC address ",
            ":".join(
                "%02x" % b for b in self.esp.MAC_address_actual # pylint: disable=consider-using-f-string,line-too-long
            ),
        )

    def loop(self):
        self.server.loop()
