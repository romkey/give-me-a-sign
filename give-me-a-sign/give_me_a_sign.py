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
import microcontroller
import rtc

from adafruit_esp32spi import adafruit_esp32spi
from adafruit_matrixportal.matrix import Matrix
from adafruit_debouncer import Debouncer
import adafruit_logging as Logger

from data import Data
from syslogger import SyslogUDPHandler
from server import Server

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

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

HTTP_SERVER_SOCKET_NUMBER = 0
NTP_SOCKET_NUMBER = 1
FREE_MEMORY_LIMIT = 10000
DEBUG = True


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
        displayio.release_displays()

        self.matrix = Matrix()
        self.display = self.matrix.display

        self._setup_buttons()
        self._setup_rtc()
        self._setup_esp()
        print(f"IP address {self.esp.pretty_ip(self.esp.ip_address)}")

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
        splash = Splash(self, "/assets/wifi.bmp")
        splash.show()
        self._connect_wifi()

        self.ip_screen = IP(self)  # pylint: disable=attribute-defined-outside-init

        if not DEBUG:
            self.ip_screen.show()

            show_until = time.monotonic_ns() + 20 * 1e9
            while True:
                self.ip_screen.loop()
                if time.monotonic_ns() > show_until:
                    break

            splash = Splash(self, "/assets/nyan-16.bmp")
            splash.show()
            time.sleep(10)

        self.clock = Clock(  # pylint: disable=attribute-defined-outside-init
            self, NTP_SOCKET_NUMBER
        )

        self.logger.addHandler(SyslogUDPHandler(self, secrets["syslogger"]))
        self.logger.info("Syslogger set up")

        self.server = Server(self)  # pylint: disable=attribute-defined-outside-init
        self.server.start()

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
        self.button1 = Debouncer(pin)

        pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        self.button2 = Debouncer(pin)

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
                "%02x" % b for b in self.esp.MAC_address_actual
            ),  # pylint: disable=consider-using-f-string,line-too-long
        )

    # fmt: off
    def loop(self) -> None: # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
    # fmt: on
        """
        This does all the work

        It allows the web server to run, checks the state of the buttons, and runs the
        state machine that decides what to display on the LED matrix
        """
        self.server.loop()
        self.tones.loop()
        gc.collect()

        if gc.mem_free() < FREE_MEMORY_LIMIT:  # pylint: disable=no-member
            self.logger.error(
                f"give_me_a_sign:low memory {gc.mem_free()}" # pylint: disable=no-member
            )  # pylint: disable=no-member

        self.button1.update()
        self.button2.update()

        if self.data.is_updated("tones"):
            self.tones.play()

        if not self.button1.value:
            self.ip_screen.show()
            self._next_up(States.IP_ADDRESS, 10)
            return

        if not self.button2.value:
            splash = Splash(self, "/assets/nyan-16.bmp")
            splash.show()
            self._next_up(States.SPLASH, 10)
            return

        if self.data.is_updated("greet"):
            if self.greeter.show():
                self.greeter.loop()
                self._next_up(States.GREET, 15)
                return

        if self.data.is_updated("message"):
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
                or self.data.age("weather") < 60 * 60
                or not self.weather.show()
            ):
                self._next_up(States.AQI, 10)

            return

        if self._loop_state == States.AQI:
            if (
                self._is_time_up()
                or self.data.age("aqi") < 60 * 60
                or not self.aqi.show()
            ):
                self._next_up(States.UVI, 10)

            return

        if self._loop_state == States.UVI:
            if self.clock.is_sundown:
                self._next_up(States.CLOCK, 20)
            elif (
                self._is_time_up()
                or self.data.age("uv") < 60 * 60
                or not self.uv_index.show()
            ):
                self._next_up(States.CLOCK, 20)

            return

        if self._loop_state == States.POLLEN:
            if (
                self._is_time_up()
                or self.data.age("pollen") < 60 * 60
                or not self.pollen.show()
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
