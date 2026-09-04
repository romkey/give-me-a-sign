# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give_me_a_sign.sign — application module for LED Matrix display
===============================================================

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

from adafruit_debouncer import Button
import adafruit_logging as Logger
import adafruit_display_text.label

from .platform import Platform
from ._paths import ASSETS_DIR
from .config import load_config
from .complication import Composer
from .registry import ModuleRegistry, discover_lib_modules

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
from .trimet import Trimet
from .store_only import StoreOnly

FREE_MEMORY_LIMIT = 10000
GC_INTERVAL_NS = 5 * 1_000_000_000
LOW_MEMORY_LOG_INTERVAL_NS = 30 * 1_000_000_000
DEBUG = False

CANVAS_WIDTH = 64
CANVAS_HEIGHT = 32

BUILTIN_MODULES = (
    Clock,
    Tones,
    Greet,
    Message,
    Image,
    Weather,
    AQI,
    UV,
    Pollen,
    Trimet,
    StoreOnly,
)


class GiveMeASign:  # pylint: disable=too-many-instance-attributes
    """
    The actual sign application
    """

    def __init__(self, display):
        self._platform = Platform(self)

        self.display = display
        self.display.root_group = None

        self._canvas_scale = max(
            1, min(display.width // CANVAS_WIDTH, display.height // CANVAS_HEIGHT)
        )
        self._canvas_x = (display.width - CANVAS_WIDTH * self._canvas_scale) // 2
        self._canvas_y = (display.height - CANVAS_HEIGHT * self._canvas_scale) // 2
        self._canvas_container = None

        self._setup_buttons()
        self._setup_rtc()

        self.logger = Logger.getLogger("default")
        self.logger.addHandler(Logger.StreamHandler())
        self.logger.setLevel(Logger.INFO)
        self.logger.info("Logger set up")

        self._config = load_config(self.logger)
        self.modules = ModuleRegistry(self)
        self._composer = None
        self._rotation = self._config["rotation"]
        self._rotation_index = 0
        self._active_interrupt = None
        self._system_state = None

        self._countdown_time = 0
        self.display_enabled = True
        self._blank_group = None
        self._next_gc_time = 0
        self._next_low_memory_log_time = 0

    @property
    def canvas_width(self) -> int:
        """Width in pixels of the virtual canvas content is laid out on."""
        return CANVAS_WIDTH

    @property
    def canvas_height(self) -> int:
        """Height in pixels of the virtual canvas content is laid out on."""
        return CANVAS_HEIGHT

    def show_group(self, group) -> None:
        """Display *group*, scaling and centering it on the physical matrix."""
        if self._canvas_scale == 1 and self._canvas_x == 0 and self._canvas_y == 0:
            self.display.root_group = group
            return

        if self._canvas_container is None:
            self._canvas_container = displayio.Group(
                scale=self._canvas_scale, x=self._canvas_x, y=self._canvas_y
            )

        container = self._canvas_container
        if not (len(container) == 1 and container[0] is group):
            while len(container) > 0:
                container.pop()
            container.append(group)

        self.display.root_group = container

    def _ensure_blank_group(self):
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
        if self.display_enabled:
            return
        self._ensure_blank_group()
        self.display.root_group = self._blank_group

    def _register_builtins(self):
        for module_cls in BUILTIN_MODULES:
            self.modules.register(module_cls(self))

    def start(self):
        """Bring the sign up: splash, WiFi, clock sync, and module setup."""
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

        self._register_builtins()
        external = discover_lib_modules() + self._config["modules"]
        self.modules.load_external(external)
        self._composer = Composer(self)

        self._platform.start_mqtt()
        self._resume_rotation()

    def _setup_buttons(self):
        pin = digitalio.DigitalInOut(board.BUTTON_UP)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        self.button1 = Button(pin)

        pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        self.button2 = Button(pin)

    def _setup_rtc(self):
        i2c = board.I2C()
        self.rtc = None
        if i2c.try_lock():
            addresses = i2c.scan()
            i2c.unlock()

            if 0x68 in addresses and 0x57 in addresses:
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
        """Run one pass of the main loop: housekeeping, buttons, and display."""
        self._platform.loop()

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

    def _loop_body(self) -> None:
        # pylint: disable=too-many-return-statements,too-many-branches
        # pylint: disable=too-many-statements
        for module in self.modules.interrupts():
            if module.SIDE_EFFECT_ONLY and module.wants_interrupt():
                module.on_side_effect()

        for module in self.modules.modules():
            if module.NEEDS_LOOP_ALWAYS:
                module.loop()

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
            self._system_state = "ip"
            self._active_interrupt = None
            self._set_countdown(10)
            return

        if not self.button2.value:
            splash = Splash(self, ASSETS_DIR + "/nyan-16.bmp")
            splash.show()
            self._system_state = "splash"
            self._active_interrupt = None
            self._set_countdown(10)
            return

        for module in self.modules.interrupts():
            if module.SIDE_EFFECT_ONLY:
                continue
            if module.wants_interrupt() and module.show():
                self._enter_interrupt(module)
                return

        if self._system_state == "ip":
            if self._is_time_up():
                self._system_state = None
                self._resume_rotation()
                return
            self.ip_screen.loop()
            return

        if self._system_state == "splash":
            if self._is_time_up():
                self._system_state = None
                self._resume_rotation()
            return

        if self._active_interrupt is not None:
            if self._is_time_up():
                self._active_interrupt = None
                self._resume_rotation()
                return
            if self._active_interrupt.ACTIVE_RENDER == "loop":
                self._active_interrupt.loop()
            return

        self._run_rotation()

    def _enter_interrupt(self, module):
        self._active_interrupt = module
        self._system_state = None
        self._set_countdown(module.duration())

    def _resume_rotation(self):
        for idx, entry in enumerate(self._rotation):
            if entry.get("type") == "module" and entry.get("module") == "clock":
                self._rotation_index = idx
                self._set_countdown(self._entry_duration(entry))
                return
        self._advance_rotation()

    def _entry_duration(self, entry):
        if entry["type"] == "composed":
            return entry["duration"]
        module = self.modules.get(entry["module"])
        if module is None:
            return 10
        duration = entry.get("duration")
        if duration is None:
            return module.DEFAULT_DURATION
        return duration

    def _can_start_entry(self, entry):
        if entry["type"] == "composed":
            return True
        module = self.modules.get(entry["module"])
        return module is not None and module.should_show()

    def _advance_rotation(self):
        count = len(self._rotation)
        for offset in range(1, count + 1):
            idx = (self._rotation_index + offset) % count
            entry = self._rotation[idx]
            if self._can_start_entry(entry):
                self._rotation_index = idx
                self._set_countdown(self._entry_duration(entry))
                return

        clock = self.modules.get("clock")
        if clock is not None:
            self._set_countdown(clock.DEFAULT_DURATION)
            clock.show()

    def _run_rotation(self):
        if not self._rotation:
            clock = self.modules.get("clock")
            if clock is not None:
                clock.loop()
            return

        entry = self._rotation[self._rotation_index]

        if self._is_time_up():
            self._advance_rotation()
            return

        if entry["type"] == "composed":
            if not self._composer.show(entry):
                self._advance_rotation()
            return

        module = self.modules.get(entry["module"])
        if module is None or not module.should_show():
            self._advance_rotation()
            return

        if module.ACTIVE_RENDER == "loop":
            module.loop()
        elif module.ACTIVE_RENDER == "show":
            if not module.show():
                self._advance_rotation()
        else:
            module.show()

    def _set_countdown(self, seconds) -> None:
        self._countdown_time = time.monotonic_ns() + seconds * 1_000_000_000

    def _is_time_up(self) -> bool:
        return time.monotonic_ns() > self._countdown_time

    @property
    def platform(self):
        """The platform object providing WiFi and board services."""
        return self._platform
