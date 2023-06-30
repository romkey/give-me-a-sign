# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
`SyslogUDPHandler` - Log messages via Syslog
====================================================

* Author: John Romkey

LEVELS = [
    (00, "NOTSET"),
    (10, "DEBUG"),
    (20, "INFO"),
    (30, "WARNING"),
    (40, "ERROR"),
    (50, "CRITICAL"),

syslog priorities
 0       Emergency: system is unusable
 1       Alert: action must be taken immediately
 2       Critical: critical conditions
 3       Error: error conditions
 4       Warning: warning conditions
 5       Notice: normal but significant condition
 6       Informational: informational messages
 7       Debug: debug-level messages
"""

import time

import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_logging import Handler


class SyslogUDPHandler(Handler):
    """
    Provides a Handler for adafruit_logging that sends messages to a Syslog server
    """

    UDP_PORT = 514
    PRIORITIES = [5, 7, 6, 4, 3, 2]

    def __init__(self, app, server) -> None:
        """
        :param app: the GiveMeASign object this belongs to
        :param server: Syslog server IP address or name
        """
        super().__init__()
        self._facility = 16
        self._app = app
        self._server = server

        socket.set_interface(app.esp)

        self._socket = socket.socket(type=socket.SOCK_DGRAM)
        self._socketaddr = socket.getaddrinfo(server, SyslogUDPHandler.UDP_PORT)[0][4]
        self._socket.connect(self._socketaddr, conntype=app.esp.UDP_MODE)

    def emit(self, record) -> None:
        """
        Construct a Syslog message witht he contents of the logging record

        Syslog packet looks like <FACILITY*8 + SEVERITY>MMM DD HH:MM:SS IPADDRESS TAG MSG

        TAG is up to 32 alphanumeric characters identifying the device

        The ESP32 Airlift UDP implementation is a little weird... UDP is connectionless,
        so we want to just reuse the socket forever. If we don't close it and reopen
        it, it seems to accumulate data and will just tack new messages onto the end
        of old ones. So we'll do this awkward close and connect each time.

        :param record: The record (message object) to be logged
        """
        try:
            self._socket.close()
            self._socket.connect(self._socketaddr, conntype=self._app.esp.UDP_MODE)

            priority = (
                self._facility * 8
                + SyslogUDPHandler.PRIORITIES[int(record.levelno / 10)]
            )

            now = self._app.clock.get_local_time()
            now = time.localtime(now)

            months = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]

            msg = f"<{priority}>{months[now.tm_mon-1]} {now.tm_mday} {now.tm_hour}:{now.tm_min}:{now.tm_sec} give-me-a-sign[{self._app.esp.pretty_ip(self._app.esp.ip_address)}] {record.msg}"  # pylint: disable=line-too-long
            print("SyslogUDPHandler: ", msg)
            self._socket.send(msg.encode("utf-8"))
        except ConnectionError:
            print("SyslogUDPHandler.emit failed")
