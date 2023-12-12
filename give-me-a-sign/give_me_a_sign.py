# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/give-me-a-sign - application module for LED Matrix display
====================================================

* Author: John Romkey
"""

import time
import gc
import board
import displayio
import digitalio
import terminalio
import microcontroller
import rtc

try:
    from platform_native import Platform
except ImportError:
    from platform_esp32spi import Platform

# except:
#  import platform_esp32spi

from adafruit_matrixportal.matrix import Matrix
from adafruit_debouncer import Button
import adafruit_logging as Logger
import adafruit_display_text.label

from data import Data

# from syslogger import SyslogUDPHandler

from clock import Clock
from greet import Greet
from splash import Splash
from weather import Weather
from ip import IP
from tones import Tones
from message import Message
from uv import UV
from aqi import AQI
from pollen import Pollen


HTTP_SERVER_SOCKET_NUMBER = 0
NTP_SOCKET_NUMBER = 1
FREE_MEMORY_LIMIT = 10000
DEBUG = False


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


class GiveMeASign:  # pylint: disable=too-many-instance-attributes
    """
    The actual sign application

    Initializes all the hardware and software and provides a
    delay-less loop that runs the state machine that decides what
    gets displayed when
    """

    def __init__(self):
        self._platform = Platform(self)

        displayio.release_displays()

        self.matrix = Matrix()
        self.display = self.matrix.display
        self.display.root_group = None

        self._setup_buttons()
        self._setup_rtc()
        self._platform.wifi_connect()

        self.data = Data()
        self.logger = Logger.getLogger("default")
        self.logger.addHandler(Logger.StreamHandler())
        self.logger.setLevel(Logger.INFO)
        self.logger.info("Logger set up")

        self._countdown_time = 0
        self._loop_state = States.CLOCK

    def start(self):
        """
        Kicks off the software side of things
        """
        print("Splash screen...")
        splash = Splash(self, "/assets/wifi.bmp")
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

            splash = Splash(self, "/assets/nyan-16.bmp")
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
                    import adafruit_pcf8523  # pylint: disable=import-outside-toplevel
                except ImportError:
                    print("Missing adafruit_pcf8523 library, hardware RTC disabled")
                else:
                    print("found PCF8523 RTC")
                    self.rtc = adafruit_pcf8523.PCF8523(i2c)
                    rtc.set_time_source(self.rtc)

        if self.rtc is None:
            self.rtc = rtc.RTC()

    # fmt: off
    def loop(self) -> None: # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
    # fmt: on
        """
        This does all the work

        It allows the web server to run, checks the state of the buttons, and runs the
        state machine that decides what to display on the LED matrix
        """
        self._platform.loop()
        self.tones.loop()
        gc.collect()

        if gc.mem_free() < FREE_MEMORY_LIMIT:  # pylint: disable=no-member
            self.logger.error(
                f"give_me_a_sign:low memory {gc.mem_free()}" # pylint: disable=no-member
            )  # pylint: disable=no-member

        self.button1.update()
        self.button2.update()

        if self.data.is_updated(Tones.KEY):
            self.tones.play()

        if self.button1.long_press:
            msg = "halted"
            self.logger.info(msg)
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=0xFF0000, text=msg
                )
            line.y = self.display.height // 2

            group = displayio.Group()
            group.append(line)
            self.display.show(group)

            while True:
                pass

        if self.button2.long_press:
            msg = "restart"
            self.logger.info(msg)
            line = adafruit_display_text.label.Label(
                terminalio.FONT, color=0xFF0000, text=msg
                )
            line.y = self.display.height // 2

            group = displayio.Group()
            group.append(line)
            self.display.show(group)

            time.sleep(2)
            microcontroller.reset()

        if not self.button1.value:
            self.ip_screen.show()
            self._next_up(States.IP_ADDRESS, 10)
            return

        if not self.button2.value:
            splash = Splash(self, "/assets/nyan-16.bmp")
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
                self._next_up(States.MESSAGE, 15)
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
                self._next_up(States.CLOCK, 20)
            elif (
                self._is_time_up()
                or self.data.age(UV.KEY) > 60 * 60
                or not self.uv_index.show(mini_clock)
            ):
                self._next_up(States.CLOCK, 20)

            return

        if self._loop_state == States.POLLEN:
            if (
                self._is_time_up()
                or self.data.age(Pollen.KEY) > 60 * 60
                or not self.pollen.show(mini_clock)  # pylint: disable=too-many-function-args
            ):
                self._next_up(States.CLOCK, 10)

            return

        self.clock.loop()
        gc.collect()

    def _set_countdown(self, seconds) -> None:
        """
        Sets the state machine's countdown in seconds
        """
        self._countdown_time = time.time() + seconds

    def _is_time_up(self) -> bool:
        """
        Returns whether the state machine's current countdown has completed
        """
        return time.time() > self._countdown_time

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
