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

DEFAULT_SERVER = "pool.ntp.org"
PORT = 123
NTP_TO_UNIX_EPOCH = 2208988800  # 1970-01-01 00:00:00


class AppNTP:
    """
    Very simple NTP client implementation for Adafruit AirLift
    network co-processors. Not general purpose, it's specific
    to this application.
    """

    def __init__(self, esp, server=DEFAULT_SERVER):
        self._esp = esp
        print("init", server)
        if server is None:
            self._server = DEFAULT_SERVER
        else:
            self._server = server

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

        print("NTP request ", self._server)

        try:
            socket.set_interface(self._esp)
            socketaddr = socket.getaddrinfo(self._server, PORT)[0][4]
            sckt = socket.socket(type=socket.SOCK_DGRAM)

            sckt.settimeout(TIMEOUT)
            sckt.connect(socketaddr, conntype=self._esp.UDP_MODE)
            sckt.send(packet)

            packet = sckt.recv(48)
            sckt.close()

            if len(packet) != 48:
                print("NTP fail ", len(packet))
                return None

        except BrokenPipeError as reason:
            print("NTP broken pipe", reason)
            return None

        except ConnectionError as reason:
            print("NTP connection", reason)
            return None

        seconds = struct.unpack_from("!I", packet, offset=len(packet) - 8)[0]
        time_response = time.localtime(seconds - NTP_TO_UNIX_EPOCH)
        print("NTP time:", time_response)
        return time_response
