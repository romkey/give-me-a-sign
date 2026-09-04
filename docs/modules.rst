.. SPDX-FileCopyrightText: 2026 John Romkey
..
.. SPDX-License-Identifier: MIT

Modules
=======

Give Me A Sign uses a module registry. Each module:

- declares the MQTT ``ENDPOINTS`` it listens to
- owns a private data store (``ModuleStore``)
- renders its own screens via ``show()`` and ``loop()``
- may declare Home Assistant entities via ``ha_entities()``
- may publish *complications*, fractional screen layouts used to compose
  screens out of several modules

Built-in modules are ``clock``, ``weather``, ``aqi``, ``uv``, ``pollen``,
``greet``, ``message``, ``image``, ``tones``, and store-only endpoints such
as ``debug`` and ``lunar``.

External modules
----------------

Copy a package named ``gmas_*`` into ``CIRCUITPY/lib/`` — for example
``lib/gmas_example/`` from ``examples/gmas_example/``. The package must
export a list of module classes:

.. code-block:: python

   MODULES = [YourModuleClass]

Each class subclasses :class:`give_me_a_sign.module.SignModule`. Extra
import names can also be listed in ``/config.json`` under ``"modules"``.

Configuration
-------------

If ``/config.json`` is missing, the sign shows the default rotation: clock
(20s), weather (10s), aqi (10s), uv (10s), pollen (10s).

.. code-block:: json

   {
     "modules": ["gmas_stocks"],
     "rotation": [
       {"module": "clock", "duration": 20},
       {"screen": {
         "name": "combo",
         "duration": 10,
         "complications": [
           {"ref": "clock.mini", "x": 32, "y": 0},
           {"ref": "aqi.eighth", "x": 0, "y": 0}
         ]
       }}
     ]
   }

Complication refs take the form ``module_name.complication_name``. Slot
sizes on the 64x32 canvas are full (64x32), half-wide (64x16), half-tall
(32x32), quarter (32x16) and eighth (32x8).

MQTT interface
--------------

Data is pushed to the sign over MQTT rather than pulled by it. Each sign
subscribes to topics under ``MQTT_TOPIC_PREFIX`` (default
``givemeasign``):

- ``{prefix}/all/module/{endpoint}`` — broadcast to every sign
- ``{prefix}/sign/{mac}/module/{endpoint}`` — per-device

Supported endpoints include ``weather``, ``message``, ``greet``, ``aqi``,
``uv``, ``pollen``, ``forecast``, ``lunar``, ``tones``, ``image``,
``timezone``, ``solar``, ``trimet`` and ``debug``. Payloads are JSON
objects; plain text is also accepted for ``message`` and ``greet``.

Per-device command topics live under ``{prefix}/sign/{mac}/``:

.. list-table::
   :header-rows: 1

   * - Topic
     - Payload
     - Effect
   * - ``reboot``
     - any
     - MCU reset
   * - ``display/set``
     - ``ON`` / ``OFF``
     - Blank or show the matrix
   * - ``time/set``
     - ISO 8601 UTC, epoch, or ``{"epoch": ...}``
     - Set the device RTC
   * - ``data/publish``
     - any
     - Publish all module data stores to ``data/state``
