# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
#
# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

# based on https://github.com/adafruit/Adafruit_CircuitPython_ESP32SPI/blob/main/examples/server/esp32spi_wsgiserver.py pylint: disable=line-too-long

"""
power-test/server - web server module for LED Matrix display
====================================================

* Author: John Romkey
"""

import json
import microcontroller

import displayio
from adafruit_display_shapes.rect import Rect
import adafruit_esp32spi.adafruit_esp32spi_wsgiserver as http_server

from http_server import SimpleWSGIApplication

class Server:
    """
    Mostly handlers for routes
    """

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app
        self._display = app.display
        self._web_app = SimpleWSGIApplication()
        self._position = { "x": 0, "y": 0 }
        self._size = .10
        self._colors = { "red": 0, "green": 0, "blue": 0 }

    def start(self) -> None:
        """
        Start the server - set all the routes and set up the web server
        """
        self._web_app.on("GET", "/", lambda environment: self._web_app.serve_file("/index.html"))
        self._web_app.on("POST",
                             "/update",
                    lambda environment: Server.update(self, environment)
                )

        http_server.set_interface(self._app.esp)
        # nofmt
        self._wsgi_server = (  # pylint: disable=attribute-defined-outside-init
            http_server.WSGIServer(80, application=self._web_app)
        )
        # fmt
        self._wsgi_server.start()

        print("server started")

    def loop(self) -> None:
        """
        Let the underlying HTTP server run

        In the event of a communications error with the ESP32, reset it
        """
        try:
            self._wsgi_server.update_poll()
        except OSError as e:
            print("ESP failure, reset", e)
            self._app.esp.reset()

    def update(self, environ) -> list:
        """
        AJAX call - take RGB and size and draw a rectangle on the screen
        """
        print("/update", environ["wsgi.input"].getvalue())

        try:
            msg = json.loads(environ["wsgi.input"].getvalue())
        except ValueError:
            print(f'server:udpate() json fail: {environ["wsgi.input"].getvalue()}')

            return ("400 Invalid JSON", [], [])

        print(msg)

        rgb = 0
        if msg["red"]:
            rgb += 0xFF0000
        if msg["green"]:
            rgb += 0x00FF00
        if msg["blue"]:
            rgb += 0x0000FF

        group = displayio.Group()

        size = float(msg["size"])
        width = int(self._display.width*size/100)
        height = self._display.height
        print(width, height)

        rect = Rect(0, 0, width, height, fill=rgb)
        group.append(rect)
        self._display.show(group)

        return ("200 OK", [], [])
