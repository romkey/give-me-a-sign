# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give_me_a_sign.sign — application module for LED Matrix display
====================================================

* Author: John Romkey
"""
# pylint: disable=wrong-import-position

import sys

_MIN_CIRCUITPYTHON = (10, 0, 0)


def _require_circuitpython_version():
    """Fail fast on unsupported CircuitPython (CP 10+). Skip on CPython for local tooling."""
    if getattr(sys.implementation, "name", "") != "circuitpython":
        return
    ver = sys.implementation.version
    if ver < _MIN_CIRCUITPYTHON:
        vstr = ".".join(str(x) for x in ver)
        raise RuntimeError(
            "Give Me A Sign requires CircuitPython "
            f"{_MIN_CIRCUITPYTHON[0]}.x or later (this build is {vstr})."
        )


_require_circuitpython_version()

import time
import gc
import board
import displayio
import digitalio
import terminalio
import microcontroller
import rtc

try:
    from .platform_native import Platform
except ImportError:
    from .platform_esp32spi import Platform

# except:
#  import platform_esp32spi

from adafruit_debouncer import Button
import adafruit_logging as Logger
import adafruit_display_text.label

from .data import Data
from ._paths import ASSETS_DIR

# from syslogger import SyslogUDPHandler

from .clock import Clock
from .greet import Greet
from .splash import Splash
from .weather import Weather
from .image import Image
from .ip import IP
from .tones import Tones
from .message import Message
from .uv import UV
from .aqi import AQI
from .pollen import Pollen

FREE_MEMORY_LIMIT = 10000
GC_INTERVAL_NS = 5 * 1_000_000_000
LOW_MEMORY_LOG_INTERVAL_NS = 30 * 1_000_000_000
DEBUG = False

# All modules lay out their content on a virtual 64x32 canvas (one standard
# panel). On larger displays - chained/tiled multiples of 64x32 - the canvas
# is integer-scaled and centered, so everything renders correctly at any size.
CANVAS_WIDTH = 64
CANVAS_HEIGHT = 32


class States:  # pylint: disable=too-few-public-methods
    """
    Simple class to just encapsulate the state variables used by the
    sign's state machine in loop()
    """

    CLOCK = 1
    IP_ADDRESS = 2
    SPLASH = 3
    GREET = 4
    MESSAGE = 5
    WEATHER = 6
    UVI = 7
    AQI = 8
    POLLEN = 9
    TRIMET = 10
    IMAGE = 11


class GiveMeASign:  # pylint: disable=too-many-instance-attributes
    """
    The actual sign application

    Initializes all the hardware and software and provides a
    delay-less loop that runs the state machine that decides what
    gets displayed when
    """

    def __init__(self, display):
        self._platform = Platform(self)

        self.display = display
        self.display.root_group = None

        # integer scale factor from the 64x32 virtual canvas to the physical
        # display, and offsets to center it (non-proportional sizes like
        # 128x32 scale by the common factor and letterbox the rest)
        self._canvas_scale = max(
            1, min(display.width // CANVAS_WIDTH, display.height // CANVAS_HEIGHT)
        )
        self._canvas_x = (display.width - CANVAS_WIDTH * self._canvas_scale) // 2
        self._canvas_y = (display.height - CANVAS_HEIGHT * self._canvas_scale) // 2
        self._canvas_container = None

        self._setup_buttons()
        self._setup_rtc()

        self.data = Data()
        self.logger = Logger.getLogger("default")
        self.logger.addHandler(Logger.StreamHandler())
        self.logger.setLevel(Logger.INFO)
        self.logger.info("Logger set up")

        self._countdown_time = 0
        self._loop_state = States.CLOCK
        self.display_enabled = True
        self._blank_group = None
        self._next_gc_time = 0
        self._next_low_memory_log_time = 0

    @property
    def canvas_width(self) -> int:
        """Width of the virtual canvas that modules lay their content out on"""
        return CANVAS_WIDTH

    @property
    def canvas_height(self) -> int:
        """Height of the virtual canvas that modules lay their content out on"""
        return CANVAS_HEIGHT

    def show_group(self, group) -> None:
        """
        Show a group laid out in virtual canvas (64x32) coordinates,
        scaled and centered to fit the physical display.

        Modules should use this instead of setting display.root_group
        directly so they work on any display size.
        """
        if self._canvas_scale == 1 and self._canvas_x == 0 and self._canvas_y == 0:
            self.display.root_group = group
            return

        if self._canvas_container is None:
            self._canvas_container = displayio.Group(
                scale=self._canvas_scale, x=self._canvas_x, y=self._canvas_y
            )

        container = self._canvas_container
        # re-showing the group that's already on screen (e.g. the clock's
        # persistent group) must not re-append it
        if not (len(container) == 1 and container[0] is group):
            while len(container) > 0:
                container.pop()
            container.append(group)

        self.display.root_group = container

    def _ensure_blank_group(self):
        """Lazily build a full-frame black group for display-off mode."""
        if self._blank_group is not None:
            return
        bitmap = displayio.Bitmap(self.display.width, self.display.height, 1)
        palette = displayio.Palette(1)
        palette[0] = 0x000000
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        group = displayio.Group()
        group.append(tile_grid)
        self._blank_group = group

    def _apply_display_mask(self):
        """When display is disabled, replace visible content with a black frame."""
        if self.display_enabled:
            return
        self._ensure_blank_group()
        self.display.root_group = self._blank_group

    def start(self):
        """
        Kicks off the software side of things
        """
        print("Splash screen...")
        splash = Splash(self, ASSETS_DIR + "/wifi.bmp")
        splash.show()
        self._platform.wifi_connect()
        print(f"IP address {self._platform.wifi_ip_address}")

        self.ip_screen = IP(self)  # pylint: disable=attribute-defined-outside-init

        if DEBUG:
            self.ip_screen.show()

            show_until = time.monotonic_ns() + 20 * 1e9
            while True:
                self.ip_screen.loop()
                if time.monotonic_ns() > show_until:
                    break

            splash = Splash(self, ASSETS_DIR + "/nyan-16.bmp")
            splash.show()
            time.sleep(10)

        self.clock = Clock(self)  # pylint: disable=attribute-defined-outside-init

        #        syslogger = os.getenv("syslogger")
        #        if syslogger is not None:
        #            self.logger.addHandler(SyslogUDPHandler(self, syslogger))
        #            self.logger.info("Syslogger set up")
        #        else:
        #            self.logger.info("No syslogger")

        self._platform.start_servers()

        self.greeter = Greet(self)  # pylint: disable=attribute-defined-outside-init
        self.weather = Weather(self)  # pylint: disable=attribute-defined-outside-init
        self.message = Message(self)  # pylint: disable=attribute-defined-outside-init
        self.uv_index = UV(self)  # pylint: disable=attribute-defined-outside-init
        self.aqi = AQI(self)  # pylint: disable=attribute-defined-outside-init
        self.tones = Tones(self)  # pylint: disable=attribute-defined-outside-init
        self.pollen = Pollen(self)  # pylint: disable=attribute-defined-outside-init
        self.image = Image(self)  # pylint: disable=attribute-defined-outside-init
        self._next_up(States.CLOCK, 20)

    def _setup_buttons(self):
        """
        Hardware setup for the buttons on the Matrix Portal board
        """
        pin = digitalio.DigitalInOut(board.BUTTON_UP)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        self.button1 = Button(pin)

        pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        self.button2 = Button(pin)

    def _setup_rtc(self):
        """
        Initialize the RTC

        Try to figure out whether we have a DS3231 or PFC8523 and
        load the correct library for it
        """
        i2c = board.I2C()
        self.rtc = None
        if i2c.try_lock():
            addresses = i2c.scan()
            i2c.unlock()

            if 0x68 in addresses and 0x57 in addresses:
                # 0x57 is an AT24C32 which is included on most DS3231 boards
                #   if this is present, assume this is a DS3231, otherwise a
                try:
                    import adafruit_ds3231  # pylint: disable=import-outside-toplevel
                except ImportError:
                    print("Missing adafruit_ds3231 library, hardware RTC disabled")
                else:
                    print("found DS3231 RTC")
                    self.rtc = adafruit_ds3231.DS3231(i2c)
                    rtc.set_time_source(self.rtc)
            elif 0x68 in addresses:
                try:
                    from adafruit_pcf8523.pcf8523 import (  # pylint: disable=import-outside-toplevel
                        PCF8523,
                    )
                except ImportError:
                    print("Missing adafruit_pcf8523 library, hardware RTC disabled")
                else:
                    print("found PCF8523 RTC")
                    self.rtc = PCF8523(i2c)
                    rtc.set_time_source(self.rtc)

        if self.rtc is None:
            self.rtc = rtc.RTC()

    def loop(self) -> None:
        """
        This does all the work

        It allows the web server to run, checks the state of the buttons, and runs the
        state machine that decides what to display on the LED matrix
        """
        self._platform.loop()
        self.tones.loop()

        now = time.monotonic_ns()
        if now > self._next_gc_time:
            self._next_gc_time = now + GC_INTERVAL_NS
            gc.collect()

            if gc.mem_free() < FREE_MEMORY_LIMIT:  # pylint: disable=no-member
                if now > self._next_low_memory_log_time:
                    self._next_low_memory_log_time = now + LOW_MEMORY_LOG_INTERVAL_NS
                    self.logger.error(
                        f"give_me_a_sign:low memory {gc.mem_free()}"  # pylint: disable=no-member
                    )

        self.button1.update()
        self.button2.update()

        try:
            self._loop_body()
        finally:
            self._apply_display_mask()

    # fmt: off
    def _loop_body(self) -> None: # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
    # fmt: on
        """
        State machine and display updates; wrapped by loop() so display-off applies
        after every iteration.
        """
        if self.data.is_updated(Tones.KEY):
            self.tones.play()

        if self.button1.long_press:
            msg = "halted"
            self.logger.info(msg)
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=0xFF0000, text=msg
                )
            line.y = self.canvas_height // 2

            group = displayio.Group()
            group.append(line)
            self.show_group(group)

            print("HALT")
            while True:
                pass

        if self.button2.long_press:
            msg = "restart"
            self.logger.info(msg)
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=0xFF0000, text=msg
                )
            line.y = self.canvas_height // 2

            group = displayio.Group()
            group.append(line)
            self.show_group(group)

            time.sleep(2)
            microcontroller.reset()

        if not self.button1.value:
            self.ip_screen.show()
            self._next_up(States.IP_ADDRESS, 10)
            return

        if not self.button2.value:
            splash = Splash(self, ASSETS_DIR + "/nyan-16.bmp")
            splash.show()
            self._next_up(States.SPLASH, 10)
            return

        if self.data.is_updated(Greet.KEY):
            if self.greeter.show():
                self.greeter.loop()
                self._next_up(States.GREET, 15)
                return

        if self.data.is_updated(Message.KEY):
            if self.message.show():
                self.message.loop()
                self._next_up(
                    States.MESSAGE, self._data_duration(Message.KEY, 15)
                )
                return

        if self.data.is_updated(Image.KEY):
            if self.image.show():
                self._next_up(States.IMAGE, self._data_duration(Image.KEY, 15))
                return

        if self._loop_state == States.MESSAGE:
            if self._is_time_up():
                self._next_up(States.CLOCK, 20)
                return

            self.message.loop()
            return

        if self._loop_state == States.GREET:
            if self._is_time_up():
                self._next_up(States.CLOCK, 20)
                return

            self.greeter.loop()
            return

        if self._loop_state == States.IMAGE:
            if self._is_time_up():
                self._next_up(States.CLOCK, 20)
            return

        if self._loop_state == States.IP_ADDRESS:
            if self._is_time_up():
                self._next_up(States.CLOCK, 20)
                return

            self.ip_screen.loop()
            return

        if self._loop_state == States.SPLASH:
            if self._is_time_up():
                self._next_up(States.CLOCK, 20)
            return

        if self._loop_state == States.CLOCK:
            if self._is_time_up():
                self._next_up(States.WEATHER, 10)
                return

            self.clock.loop()
            return

        if self._loop_state == States.WEATHER:
            if (
                self._is_time_up()
                or self.data.age(Weather.KEY) > 60 * 60
                or not self.weather.show()
            ):
                self._next_up(States.AQI, 10)

            return

        mini_clock = self.clock.mini_clock()

        if self._loop_state == States.AQI:
            if (
                self._is_time_up()
                or self.data.age(AQI.KEY) > 60 * 60
                or not self.aqi.show(mini_clock)
            ):
                self._next_up(States.UVI, 10)

            return

        if self._loop_state == States.UVI:
            if self.clock.is_sundown:
                self._next_up(States.POLLEN, 10)
            elif (
                self._is_time_up()
                or self.data.age(UV.KEY) > 60 * 60
                or not self.uv_index.show(mini_clock)
            ):
                self._next_up(States.POLLEN, 10)

            return

        if self._loop_state == States.POLLEN:
            if (
                self._is_time_up()
                or self.data.age(Pollen.KEY) > 60 * 60
                or not self.pollen.show(mini_clock)
            ):
                self._next_up(States.CLOCK, 20)

            return

        self.clock.loop()

    def _data_duration(self, key, default) -> int:
        """
        Return the optional "duration" field (seconds) from the data stored
        under key, or default if it's missing or invalid
        """
        item = self.data.get_item(key)
        try:
            duration = int(item["duration"])
        except (KeyError, TypeError, ValueError):
            return default

        return duration if duration > 0 else default

    def _set_countdown(self, seconds) -> None:
        """
        Sets the state machine's countdown in seconds

        Uses the monotonic clock: time.time() jumps when NTP corrects the
        RTC, which could freeze the sign on one screen for hours
        """
        self._countdown_time = time.monotonic_ns() + seconds * 1_000_000_000

    def _is_time_up(self) -> bool:
        """
        Returns whether the state machine's current countdown has completed
        """
        return time.monotonic_ns() > self._countdown_time

    def _next_up(self, state, duration) -> None:
        """
        Tell the loop state machine we's up next and for how many seconds
        """
        self._loop_state = state
        self._set_countdown(duration)

    @property
    def debug(self) -> bool:
        """
        Returns contents of debug flag, if set
        True -> debugging mode
        False -> not debugging mode, or not set
        """
        debug = self.data.get_item("debug")
        if debug is None:
            return False

        try:
            return debug["debug"]
        except KeyError:
            return False

    @property
    def platform(self):
        """
        Return the platform object
        """
        return self._platform
