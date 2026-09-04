# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/registry - module registration and discovery
===========================================================

* Author: John Romkey
"""

import gc
import os


class ModuleRegistry:
    """
    Registry of SignModule instances keyed by NAME and MQTT endpoint.
    """

    def __init__(self, app):
        self._app = app
        self._modules = []
        self._by_name = {}
        self._by_endpoint = {}

    def register(self, module):
        """Add *module* to the registry. Return False on a duplicate name or endpoint."""
        name = module.NAME
        if not name:
            self._app.logger.error("module:register missing NAME")
            return False

        if name in self._by_name:
            self._app.logger.error(f"module:register duplicate NAME {name}")
            return False

        for endpoint in module.ENDPOINTS:
            if endpoint in self._by_endpoint:
                self._app.logger.error(
                    f"module:register endpoint {endpoint} already claimed"
                )
                return False

        self._modules.append(module)
        self._by_name[name] = module
        for endpoint in module.ENDPOINTS:
            self._by_endpoint[endpoint] = module
        return True

    def get(self, name):
        """Return the registered module named *name*, or ``None``."""
        return self._by_name.get(name)

    def modules(self):
        """Every registered module, in registration order."""
        return tuple(self._modules)

    def by_endpoint(self, endpoint):
        """Return the module that claims the MQTT *endpoint*, or ``None``."""
        return self._by_endpoint.get(endpoint)

    def interrupts(self):
        """Registered modules that can interrupt the rotation."""
        return tuple(m for m in self._modules if m.IS_INTERRUPT)

    def load_external(self, import_names):
        """Import each ``gmas_*`` package by name and register its ``MODULES``."""
        for name in import_names:
            try:
                package = __import__(name)
            except (ImportError, OSError, ValueError) as error:
                self._app.logger.error(f"module:import {name} failed: {error}")
                continue

            module_list = getattr(package, "MODULES", None)
            if not module_list:
                self._app.logger.error(f"module:import {name} missing MODULES")
                continue

            for module_cls in module_list:
                try:
                    instance = module_cls(self._app)
                except Exception as error:  # pylint: disable=broad-exception-caught
                    self._app.logger.error(
                        f"module:instantiate {module_cls} failed: {error}"
                    )
                    continue
                self.register(instance)

            gc.collect()


def discover_lib_modules():
    """
    Return import names for /lib packages matching the gmas_* convention.
    """
    names = []
    try:
        entries = os.listdir("/lib")
    except OSError:
        return names

    for entry in entries:
        if not entry.startswith("gmas_"):
            continue
        if entry.endswith(".py"):
            names.append(entry[:-3])
        elif entry.endswith(".mpy"):
            names.append(entry[:-4])
        else:
            names.append(entry)
    return names
