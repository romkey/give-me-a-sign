# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/tones - tones module for LED Matrix display
====================================================

* Author: John Romkey

See https://docs.circuitpython.org/en/latest/shared-bindings/pwmio/index.html
and https://learn.adafruit.com/using-piezo-buzzers-with-circuitpython-arduino/circuitpython
"""

import time
import board
import pwmio


class Tones:
    """
    Managing playing tones on a piezoelectric buzzer
    """

    KEY = "tones"

    FULL_ON = 2**15
    FULL_OFF = 0

    def __init__(self, app):
        self._app = app
        self._current_index = None
        self._pwm = pwmio.PWMOut(board.A4, variable_frequency=True)
        self._pwm.duty_cycle = Tones.FULL_OFF
        self._tones = []
        self._play_until = 0

    def play(self) -> bool:
        """
        Read tones from Data and begin playing them

        Returns False if nothing to do, True otherwise

        frequency: KHz
        duration: seconds
        volume: %

        .. code-block:: python
        { tones: [
                    { "frequency": 400, "duration": 0.5, volume: 100 },
                    { "frequency": 5500, "duration": 1.2, volume: 100 }
                 ]
        }
        """
        data = self._app.data.get_item(Tones.KEY)
        self._app.data.clear_updated(Tones.KEY)

        # validate now: loop() runs on every app loop pass, so a malformed
        # payload crashing there would freeze the whole sign (with the
        # buzzer possibly stuck on)
        try:
            tones = data["tones"]
            for tone in tones:
                int(tone["frequency"])
                float(tone["duration"])
                float(tone["volume"])
        except (KeyError, TypeError, ValueError):
            print("tones: bad data", data)
            return False

        self._tones = data
        self._current_index = -1
        self._play_until = time.monotonic()

        return True

    def loop(self) -> None:
        """
        loop function

        check if it's time to play the next tone
        """
        if self._current_index is None:
            return

        if self._play_until > time.monotonic():
            return

        self._current_index += 1

        if self._current_index == len(self._tones["tones"]):
            self._current_index = None
            self._pwm.duty_cycle = Tones.FULL_OFF
            return

        self._pwm.frequency = int(
            self._tones["tones"][self._current_index]["frequency"]
        )
        self._pwm.duty_cycle = int(
            (self._tones["tones"][self._current_index]["volume"] / 100.0)
            * Tones.FULL_ON
        )
        self._play_until = (
            time.monotonic() + self._tones["tones"][self._current_index]["duration"]
        )
