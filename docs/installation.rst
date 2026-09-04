.. SPDX-FileCopyrightText: 2026 John Romkey
..
.. SPDX-License-Identifier: MIT

Installation
============

Hardware
--------

Give Me A Sign targets boards with **native WiFi** and enough RAM for the
full application, such as the `Adafruit Matrix Portal S3
<https://www.adafruit.com/product/5778>`_ driving a 64x32 LED matrix. The
older Matrix Portal M4 (SAMD51 plus AirLift co-processor) is not supported
— it does not have enough RAM to run the sign reliably.

Displays built from multiples of a 64x32 panel work too: chain panels for
more width, stack them for more height, or use 64-row panels. Describe the
geometry in ``settings.toml``:

.. code-block:: toml

   MATRIX_WIDTH = 128         # total pixels across (chained panels)
   MATRIX_PANEL_HEIGHT = 32   # rows per panel: 32, or 64 (needs ADDR E)
   MATRIX_TILE = 2            # rows of panels stacked vertically
   MATRIX_SERPENTINE = true   # alternate panel rows rotated 180 degrees
   MATRIX_BIT_DEPTH = 2       # color depth; higher uses more RAM/CPU

Content is laid out on a virtual 64x32 canvas and integer-scaled to fit the
display, centered.

Installing the library
----------------------

The application ships as a CircuitPython library package named
``give_me_a_sign``. Install it on ``CIRCUITPY`` under
``lib/give_me_a_sign/`` with `circup
<https://learn.adafruit.com/keep-your-circuitpython-libraries-on-devices-up-to-date-with-circup/install-command>`_.

From a clone of the repository, for development:

.. code-block:: shell

   circup install -r requirements-circuitpython.txt ./give_me_a_sign --py --upgrade

From a release zip, using the precompiled ``.mpy`` package:

.. code-block:: shell

   unzip give-me-a-sign-10.x-mpy-0.5.2.zip
   circup install -r requirements-circuitpython.txt \
     ./give-me-a-sign-10.x-mpy-0.5.2/lib/give_me_a_sign --upgrade

Bundle dependencies are not inside the release zip; circup pulls them from
the official CircuitPython bundles.

Finishing the install
---------------------

1. Install CircuitPython on the board and mount ``CIRCUITPY``.
2. Install the library as above.
3. Copy ``examples/code.py`` to the root of ``CIRCUITPY`` (or merge it into
   your own ``code.py``) and add ``settings.toml`` as needed.
4. Optionally copy ``examples/config.json`` to ``/config.json`` on
   ``CIRCUITPY`` to customize which modules rotate and for how long.

Usage
-----

The example ``code.py`` builds an ``rgbmatrix`` display, hands it to
:class:`give_me_a_sign.sign.GiveMeASign`, and calls ``loop()`` forever:

.. code-block:: python

   from give_me_a_sign import GiveMeASign

   app = GiveMeASign(display)

   while True:
       app.loop()

See ``examples/code.py`` for the full version, which also handles
``MemoryError`` and ``OSError`` and reboots on repeated failures.
