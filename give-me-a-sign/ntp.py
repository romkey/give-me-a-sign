# SPDX-FileCopyrightText: 2023 John Romkey
# SPDX-License-Identifier: MIT

# adapted from https://github.com/adafruit/Adafruit_CircuitPython_ESP32SPI/blob/main/examples/esp32spi_udp_client.py pylint: disable=line-too-long

"""
give-me-a-sign/ntp - Network Time Protocol module for LED Matrix display
====================================================

* Author: John Romkey
"""

import struct
import time

import adafruit_esp32spi.adafruit_esp32spi_socket as socket

TIMEOUT = 5

HOST = "pool.ntp.org"
PORT = 123
NTP_TO_UNIX_EPOCH = 2208988800  # 1970-01-01 00:00:00


class NTP:
    """
    Very simple NTP client implementation for Adafruit AirLift
    network co-processors. Not general purpose, it's specific
    to this application.
    """

    def __init__(self, esp, rtc, socket_number=0):
        self._esp = esp
        self._rtc = rtc

        socket.set_interface(esp)
        self._socketaddr = socket.getaddrinfo(HOST, PORT)[0][4]
        self._s = socket.socket(type=socket.SOCK_DGRAM, socknum=socket_number)

        self._s.settimeout(TIMEOUT)
        self._s.connect(self._socketaddr, conntype=self._esp.UDP_MODE)

    def update(self) -> None:
        """
        Query the NTP server; on success set the RTC to the current time

        One weird thing, we have to close and re-open the socket to send a new
        message. If we don't, it tacks the new message on the end of previous
        messages.
        """
        packet = bytearray(48)
        packet[0] = 0b00100011
        for i in range(1, len(packet)):
            packet[i] = 0

        try:
            self._s.close()
            self._s.connect(self._socketaddr, conntype=self._esp.UDP_MODE)
            self._s.send(packet)
        except ConnectionError:
            print("NTP connect fail")
            return

        packet = self._s.recv(48)
        if len(packet) != 48:
            print("NTP fail ", len(packet))
            return

        seconds = struct.unpack_from("!I", packet, offset=len(packet) - 8)[0]
        self._rtc.datetime = time.localtime(seconds - NTP_TO_UNIX_EPOCH)
        print("NTP time:", self._rtc.datetime)
