# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/native-server - web server module for LED Matrix display
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

import wifi
import socketpool
from adafruit_httpserver import (
    Server,
    Route,
    Request,
    Response,
    FileResponse,
    JSONResponse,
    Redirect,
    Status,
)

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


class AppServer:
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
        pool = socketpool.SocketPool(wifi.radio)
        self._http_server = Server(pool)

    def start(self) -> None:
        """
        Start the server - set all the routes and set up the web server
        """
        for endpoint in self.STORE_ENDPOINTS:
            stash = self

            self._http_server.add_routes(
                [
                    Route(
                        f"/{endpoint}",
                        "POST",
                        lambda request, key=endpoint: stash.store_data(request, key),
                    )
                ]
            )

        self._http_server.add_routes(
            [
                Route("/reboot", "GET", lambda request: microcontroller.reset()),
                Route("/info", "GET", lambda request: stash.info(request)),
                Route("/data", "GET", lambda request: stash.data(request)),
                Route("/set-time", "POST", lambda request: stash.set_time(request)),
                Route("/image", "POST", lambda request: stash.image(request)),
            ]
        )
        self._http_server.start(str(wifi.radio.ipv4_address))

    def loop(self) -> None:
        """
        Let the underlying HTTP server run
        """
        try:
            self._http_server.poll()
        except OSError:
            self._app.esp.reset()

    def store_data(self, request, key) -> list:
        """
        Reusable generic handler called by several routes, which
        stores an object represented in JSON in Data associated
        with a particular key
        """
        print(dir(request))
        body = request.body.decode()
        print(body)

        try:
            msg = json.loads(body)
        except ValueError:
            self._app.logger.error(
                f"server:store_data({key}) store_data failed: {body}"
            )

            return ("400 Invalid JSON", [], [])

        self._app.data.set_item(key, msg)

        self._app.logger.info(f"server:store_data({key}) got JSON: {msg}")

        return Response(request, status=Status(200, "OK"))

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

    def info(self, request) -> list:  # pylint: disable=unused-argument
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

        return Response(
            request,
            status=Status(200, "OK"),
            content_type="application/json",
            body=json.dumps(info),
        )

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
