# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/tones - tones module for LED Matrix display
==========================================================

* Author: John Romkey
"""

import time
import board
import pwmio

from .module import SignModule


class Tones(SignModule):
    """
    Managing playing tones on a piezoelectric buzzer
    """

    NAME = "tones"
    KEY = "tones"
    ENDPOINTS = (KEY,)
    IS_INTERRUPT = True
    SIDE_EFFECT_ONLY = True
    NEEDS_LOOP_ALWAYS = True

    FULL_ON = 2**15
    FULL_OFF = 0

    def __init__(self, app):
        super().__init__(app)
        self._current_index = None
        self._pwm = pwmio.PWMOut(board.A4, variable_frequency=True)
        self._pwm.duty_cycle = Tones.FULL_OFF
        self._tones = []
        self._play_until = 0

    def on_side_effect(self):
        self.play()

    def play(self) -> bool:
        """Queue the tones from the last payload. Return False if it was unusable."""
        data = self.store.get_item(Tones.KEY)
        self.store.clear_updated(Tones.KEY)

        try:
            tones = data["tones"]
            normalized = []
            for tone in tones:
                normalized.append(
                    (
                        int(tone["frequency"]),
                        float(tone["duration"]),
                        float(tone["volume"]),
                    )
                )
        except (KeyError, TypeError, ValueError):
            print("tones: bad data", data)
            return False

        self._tones = normalized
        self._current_index = -1
        self._play_until = time.monotonic()
        return True

    def loop(self) -> None:
        if self._current_index is None:
            return

        if self._play_until > time.monotonic():
            return

        self._current_index += 1

        if self._current_index == len(self._tones):
            self._current_index = None
            self._pwm.duty_cycle = Tones.FULL_OFF
            return

        frequency, duration, volume = self._tones[self._current_index]
        self._pwm.frequency = frequency
        self._pwm.duty_cycle = int((volume / 100.0) * Tones.FULL_ON)
        self._play_until = time.monotonic() + duration
