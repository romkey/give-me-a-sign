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

# import wifi
# import socketpool
from adafruit_httpserver import Server, Route, Response, JSONResponse, Status

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

    # pylint: disable=duplicate-code
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
        #        pool = socketpool.SocketPool(wifi.radio)
        #        self._http_server = Server(pool)
        self._http_server = Server(app.platform.get_socket())

    def start(self) -> None:
        """
        Start the server - set all the routes and set up the web server
        """
        for endpoint in self.STORE_ENDPOINTS:
            self._http_server.add_routes(
                [
                    Route(
                        f"/{endpoint}",
                        "POST",
                        lambda request, key=endpoint: self.store_data(request, key),
                    )
                ]
            )

        self._http_server.add_routes(
            [
                Route("/reboot", "GET", lambda request: microcontroller.reset()),
                # pylint: disable=unnecessary-lambda
                Route("/info", "GET", lambda request: self.info(request)),
                Route("/data", "GET", lambda request: self.data(request)),
                Route("/set-time", "POST", lambda request: self.set_time(request)),
                Route("/image", "POST", lambda request: self.image(request)),
            ]
        )
        #        self._http_server.start(str(wifi.radio.ipv4_address))
        self._http_server.start(self._app.platform.wifi_ip_address)

    def loop(self) -> None:
        """
        Let the underlying HTTP server run
        """
        self._http_server.poll()

    def store_data(self, request, key) -> list:
        """
        Reusable generic handler called by several routes, which
        stores an object represented in JSON in Data associated
        with a particular key
        """
        body = request.body.decode()

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

    def set_time(self, request) -> list:
        """
        Handler to set the time, passed in as JSON

        .. code-block:: python
        { time: integer }
        """
        body = request.body.decode()

        try:
            msg = json.loads(body)
        except ValueError:
            print(f"invalid JSON {body}")

            self._app.logger.error(f"server:set_time: invalid JSON {body}")

            return Response(request, status=Status(400, "Invalid JSON"))

        try:
            then = time.localtime(msg["time"])
        except KeyError:
            return Response(request, status=Status(400, "Missing key 'time'"))

        self._app.rtc.datetime = then

        self._app.logger.info(f'server:set_time({msg["time"]})')
        return Response(request, status=Status(200, "OK"))

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
            "wifi": {
                "ssid": self._app.platform.wifi_ssid,
                "bssid": self._app.platform.wifi_bssid,
                "rssi": self._app.platform.wifi_rssi,
                "mac": self._app.platform.mac_address,
                "ip": self._app.platform.ip_address,
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

        return JSONResponse(request, data=info)

    def data(self, request) -> list:  # pylint: disable=unused-argument
        """
        Return all the data in Data, for debugging
        """
        self._app.logger.info(f"server:get_data -> {self._app.data.all()}")

        return JSONResponse(request, data=self._app.data.all())
