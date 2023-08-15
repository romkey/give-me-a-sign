# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
#
# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

# based on https://github.com/adafruit/Adafruit_CircuitPython_ESP32SPI/blob/main/examples/server/esp32spi_wsgiserver.py pylint: disable=line-too-long

"""
give-me-a-sign/server - web server module for LED Matrix display
====================================================

* Author: John Romkey
"""

import os
import gc
import sys
import time
import json
import storage
import microcontroller
import board

import adafruit_esp32spi.adafruit_esp32spi_wsgiserver as http_server
from http_server import SimpleWSGIApplication

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

"""
Web server

Provides endpoints for managing the sign and for pushing
data to it (like weather, Air Quality Index, etc)
"""


class Server:
    """
    Mostly handlers for routes
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
        Clock.KEY_NTP,
        Tones.KEY,
        Trimet.KEY,
        UV.KEY,
        Weather.KEY,
    ]

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app
        self._web_app = SimpleWSGIApplication()

    def start(self) -> None:
        """
        Start the server - set all the routes and set up the web server
        """
        for endpoint in self.STORE_ENDPOINTS:
            self._web_app.on(
                "POST",
                f"/{endpoint}",
                lambda environment, key=endpoint: Server.store_data(
                    self, environment, key
                ),
            )

        self._web_app.on("GET", "/reboot", lambda environment: microcontroller.reset())
        self._web_app.on(
            "GET", "/info", lambda environment: Server.info(self, environment)
        )
        self._web_app.on(
            "GET", "/data", lambda environment: Server.data(self, environment)
        )
        self._web_app.on(
            "POST", "/set-time", lambda environment: Server.set_time(self, environment)
        )
        self._web_app.on(
            "POST", "/image", lambda environment: Server.image(self, environment)
        )

        http_server.set_interface(self._app.esp)
        # nofmt
        self._wsgi_server = (  # pylint: disable=attribute-defined-outside-init
            http_server.WSGIServer(80, application=self._web_app)
        )
        # fmt
        self._wsgi_server.start()

    def loop(self) -> None:
        """
        Let the underlying HTTP server run

        In the event of a communications error with the ESP32, reset it
        """
        try:
            self._wsgi_server.update_poll()
        except OSError:
            self._app.logger.error("ESP failure, reset")
            self._app.esp.reset()

    def store_data(self, environ, key) -> list:
        """
        Reusable generic handler called by several routes, which
        stores an object represented in JSON in Data associated
        with a particular key
        """
        print(environ["wsgi.input"].getvalue())

        try:
            msg = json.loads(environ["wsgi.input"].getvalue())
        except ValueError:
            self._app.logger.error(
                f'server:store_data({key}) store_data failed: {environ["wsgi.input"].getvalue()}'
            )

            return ("400 Invalid JSON", [], [])

        self._app.data.set_item(key, msg)

        self._app.logger.info(f"server:store_data({key}) got JSON: {msg}")

        return ("200 OK", [], [])

    def set_time(self, environ) -> list:
        """
        Handler to set the time, passed in as JSON

        .. code-block:: python
        { time: integer }
        """
        print(environ["wsgi.input"].getvalue())

        try:
            msg = json.loads(environ["wsgi.input"].getvalue())
        except ValueError:
            print("invalid JSON", environ["wsgi.input"].getvalue())

            self._app.logger.error(
                f'server:set_time: invalid JSON {environ["wsgi.input"].getvalue()}'
            )

            return ("400 Invalid JSON", [], [])

        try:
            then = time.localtime(msg["time"])
        except KeyError:
            return ("400 Missing key 'time'", [], [])

        self._app.rtc.datetime = then

        self._app.logger.info(f'server:set_time({msg["time"]})')

        return ("200 OK", [], [])

    # /image?duration=seconds&animate=true/false
    # body is file
    def image(self, environ) -> list:
        """
        Handler for uploading an image file

        Work in progress

        The file should be the body of the POST. CGI parameters
        - animate=bool - whether or not to aniamte the image
        - interval=integer - interval between frames in ms
        - x=integer - X origin of image
        - y=integer - Y origin of image
        - duration=integer - seconds image should be displayed for
        """
        print("image!")
        print(environ)

        if not "CONTENT_TYPE" in environ:
            print("No content-type")
            return ("400 Missing Content-Type", [], [])

        content_type = environ["CONTENT_TYPE"]
        words = content_type.split("/")
        if not words[1] in ["bmp", "gif", "png"]:
            print("bad content-type")
            return ("400 Invalid image type, accept only bmp, gif and png", [], [])

        suffix = words[1]
        params = environ["QUERY_STRING"].split("&")

        print("about to save image")

        storage.remount("/", False)
        filename = "/assets/uploaded_image." + suffix
        with open(filename, "w") as file:
            file.write(environ["wsgi.input"].getvalue())

        print("saved!")

        storage.remount("/", True)

        self._app.data.set_item(
            "image",
            {
                "file": filename,
                "animate": params["animate"],
                "interval": params["interval"],
                "duration": params["duration"],
                "x": params["x"],
                "y": params["y"],
            },
        )
        return ("200 OK", [], [])

    def info(self, environ) -> list:  # pylint: disable=unused-argument
        """
        Return information about the sign including version numbers, current status,
        free resources
        """
        flash = os.statvfs("/")
        flash_size = flash[0] * flash[2]
        flash_free = flash[0] * flash[3]

        info = {
            "time": {
                "uptime": time.monotonic_ns(),
                "time_utc": time.time(),
                "timezone_offset": self._app.clock.timezone_offset,
            },
            "free_memory": gc.mem_free(),  # pylint: disable=no-member
            "flash": {"free": flash_free, "size": flash_size},
            "rtc": self._app.rtc.__class__.__name__,
            "esp32_firmware": self._app.esp.firmware_version.decode(),
            "wifi": {
                "ssid": self._app.esp.ssid.decode(),
                "bssid": ":".join(
                    "%02x" % b
                    for b in self._app.esp.bssid  # pylint: disable=consider-using-f-string
                ),
                "rssi": self._app.esp.rssi,
                "mac": ":".join(
                    "%02x" % b
                    for b in self._app.esp.MAC_address_actual  # pylint: disable=consider-using-f-string
                ),
                "ip": self._app.esp.pretty_ip(self._app.esp.ip_address),
            },
            "platform": {
                "python_version": sys.version,
                "circuit_python_version": ".".join(
                    [str(i) for i in sys.implementation[1]]
                ),
                "platform": sys.platform,
                "board": board.board_id,
            },
            "display": {
                "height": self._app.display.height,
                "width": self._app.display.width,
            },
        }

        self._app.logger.info(f"server:get_info -> {info}")

        return ("200 Success", [("Content-type", "application/json")], json.dumps(info))

    def data(self, environ) -> list:  # pylint: disable=unused-argument
        """
        Return all the data in Data, for debugging
        """
        self._app.logger.info(f"server:get_data -> {self._app.data.all()}")

        return (
            "200 Success",
            [("Content-type", "application/json")],
            json.dumps(self._app.data.all()),
        )
