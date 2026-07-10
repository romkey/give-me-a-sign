# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Minimal ``pwmio`` stub for host-side unit tests."""


class PWMOut:
    instances = []

    def __init__(self, pin, variable_frequency=True):
        self.pin = pin
        self.variable_frequency = variable_frequency
        self.duty_cycle = 0
        self.frequency = 0
        PWMOut.instances.append(self)

    @classmethod
    def reset(cls):
        cls.instances.clear()
