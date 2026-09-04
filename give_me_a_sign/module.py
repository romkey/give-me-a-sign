# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/module - base class and per-module data store
============================================================

* Author: John Romkey
"""

import gc
import json
import time
import storage


class ModuleStore:
    """
    Per-module data store with the same semantics as the legacy Data class.
    """

    SAVE_FILE = "/data.json"
    KEY_DATA = "data"
    KEY_UPDATED = "updated"
    KEY_LAST_UPDATED = "last_updated"

    # endpoints is accepted for symmetry with SignModule.ENDPOINTS; the store
    # itself keys off whatever is passed to set_item().
    def __init__(
        self, endpoints=(), persistent_keys=()
    ):  # pylint: disable=unused-argument
        self._data = {}
        self._persistent_keys = tuple(persistent_keys)
        if self._persistent_keys:
            self._restore()

    def has_item(self, key) -> bool:
        """True when *key* holds data."""
        entry = self._data.get(key)
        return isinstance(entry, dict) and ModuleStore.KEY_DATA in entry

    def set_item(self, key, data) -> None:
        """Store *data* under *key* and mark it updated."""
        self._check_key(key)
        self._data[key][ModuleStore.KEY_DATA] = data
        self._data[key][ModuleStore.KEY_UPDATED] = True
        self._data[key][ModuleStore.KEY_LAST_UPDATED] = time.time()
        if key in self._persistent_keys:
            self._save()

    def get_item(self, key, default=None):
        """Return the data stored under *key*, or *default*."""
        try:
            return self._data[key][ModuleStore.KEY_DATA]
        except KeyError:
            return default

    def is_updated(self, key) -> bool:
        """True when *key* has changed since the last :meth:`clear_updated`."""
        try:
            return self._data[key][ModuleStore.KEY_UPDATED]
        except KeyError:
            return False

    def last_updated(self, key) -> int:
        """Epoch time at which *key* was last set, or 0."""
        try:
            return self._data[key][ModuleStore.KEY_LAST_UPDATED]
        except KeyError:
            return 0

    def age(self, key) -> int:
        """Seconds since *key* was last set."""
        return time.time() - self.last_updated(key)

    def newest_age(self) -> int:
        """Age of the most recently updated endpoint key, or a large value if empty."""
        ages = [self.age(key) for key in self._data if self.has_item(key)]
        if not ages:
            return 10**12
        return min(ages)

    def clear_updated(self, key) -> None:
        """Clear the updated flag on *key*."""
        try:
            if not self._data[key][ModuleStore.KEY_UPDATED]:
                return
            self._data[key][ModuleStore.KEY_UPDATED] = False
        except KeyError:
            return

    def all(self) -> dict:
        """Return the raw backing dict of every stored key."""
        return self._data

    def _check_key(self, key) -> None:
        if key in self._data:
            return
        self._data[key] = {}
        self._data[key][ModuleStore.KEY_LAST_UPDATED] = 0
        self._data[key][ModuleStore.KEY_UPDATED] = False

    def _save(self) -> bool:
        if not self._persistent_keys:
            return False

        existing = {}
        try:
            with open(ModuleStore.SAVE_FILE, "r") as file:
                existing = json.loads(file.read())
        except OSError:
            existing = {}
        except ValueError:
            existing = {}

        if not isinstance(existing, dict):
            existing = {}

        for key in self._persistent_keys:
            if key in self._data:
                existing[key] = self._data[key]

        try:
            storage.remount("/", False)
        except RuntimeError:
            return False

        gc.collect()

        try:
            with open(ModuleStore.SAVE_FILE, "w") as file:
                file.write(json.dumps(existing))
        except OSError:
            return False
        finally:
            gc.collect()
            storage.remount("/", True)

        return True

    def _restore(self) -> bool:
        try:
            with open(ModuleStore.SAVE_FILE, "r") as file:
                saved = json.loads(file.read())
        except OSError:
            return False
        except ValueError:
            return False

        if not isinstance(saved, dict):
            return False

        for key in self._persistent_keys:
            entry = saved.get(key)
            if not isinstance(entry, dict) or ModuleStore.KEY_DATA not in entry:
                continue
            self._data[key] = entry
            entry[ModuleStore.KEY_UPDATED] = False

        return True


class SignModule:  # pylint: disable=too-few-public-methods
    """
    Base class for Give Me A Sign display and data modules.
    """

    NAME = ""
    ENDPOINTS = ()
    PERSISTENT_KEYS = ()
    IS_INTERRUPT = False
    SIDE_EFFECT_ONLY = False
    STALE_SECONDS = None
    DEFAULT_DURATION = 10
    NEEDS_LOOP_ALWAYS = False
    ACTIVE_RENDER = "show"  # "show", "loop", or "once"

    def __init__(self, app):
        self._app = app
        self.store = ModuleStore(self.ENDPOINTS, persistent_keys=self.PERSISTENT_KEYS)

    def receive(self, endpoint, raw) -> None:
        """Normalize and store an MQTT payload delivered to *endpoint*."""
        data = self.normalize_payload(endpoint, raw)
        if data is None:
            self._app.logger.error(
                f"module:{self.NAME}:receive({endpoint}) bad payload"
            )
            return
        self.store.set_item(endpoint, data)
        self._app.logger.info(f"module:{self.NAME}:receive({endpoint})")
        self._app.logger.info(data)

    def normalize_payload(
        self, endpoint, raw
    ):  # pylint: disable=unused-argument,no-self-use
        """Parse a raw MQTT payload; return ``None`` if it is unusable."""
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def show(self) -> bool:  # pylint: disable=no-self-use
        """Render this module's screen. Return True if something was displayed."""
        return False

    def loop(self):  # pylint: disable=no-self-use
        """Called repeatedly while this module's screen is on display."""

    def background(self):  # pylint: disable=no-self-use
        """
        Periodic upkeep, run every pass whether or not this module is showing.

        Use this for work that must not stop when the module is off screen —
        clock NTP resync, for example. It must not draw: the module that owns
        the display calls :meth:`show` or :meth:`loop` for that.
        """

    def on_side_effect(self):
        """Called when SIDE_EFFECT_ONLY and new data arrives (e.g. tones)."""

    def wants_interrupt(self) -> bool:
        """True when this interrupt module has new data to show right now."""
        if not self.IS_INTERRUPT:
            return False
        for endpoint in self.ENDPOINTS:
            if self.store.is_updated(endpoint):
                return True
        return False

    def duration(self) -> int:
        """Seconds to display this module, from the payload or the class default."""
        for endpoint in self.ENDPOINTS:
            item = self.store.get_item(endpoint)
            if not isinstance(item, dict):
                continue
            try:
                value = int(item["duration"])
            except (KeyError, TypeError, ValueError):
                continue
            if value > 0:
                return value
        return self.DEFAULT_DURATION

    def is_stale(self) -> bool:
        """True when this module's newest data is older than ``STALE_SECONDS``."""
        if self.STALE_SECONDS is None:
            return False
        if not self.ENDPOINTS:
            return False
        return self.store.newest_age() > self.STALE_SECONDS

    def should_show(self) -> bool:
        """True when this module should take a turn in the rotation."""
        return not self.is_stale()

    def ha_entities(self):  # pylint: disable=no-self-use
        """Home Assistant autodiscovery entities this module provides."""
        return []

    def complications(self):  # pylint: disable=no-self-use
        """Complications this module publishes for composed screens."""
        return []
