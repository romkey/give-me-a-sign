.. SPDX-FileCopyrightText: 2026 John Romkey
..
.. SPDX-License-Identifier: MIT

Give Me A Sign
==============

Give Me A Sign! is a CircuitPython application for LED matrix info signs
designed for hacker and makerspaces. The sign mostly looks like a clock,
and displays messages, weather, air quality, pollen, UV index and transit
information that other systems push to it over MQTT.

Data is pushed to the sign rather than pulled by it: a more capable
computer (typically Home Assistant) does the fetching and formatting, and
the sign concerns itself with display.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   modules
   api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
