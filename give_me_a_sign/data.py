# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/data - data storage for LED Matrix display
====================================================

* Author: John Romkey
"""

import time
import gc
import json
import storage


class Data:
    """
    A simple data store which remembers when a key's value
    was last updated and provides convenience methods for checking whether
    a key's valued has changed and the value's age
    """

    SAVE_FILE = "/data.json"

    KEY_DATA = "data"
    KEY_UPDATED = "updated"
    KEY_LAST_UPDATED = "last_updated"

    def __init__(self):
        self._data = {}

        self._restore()

    def has_item(self, key) -> bool:
        """True if the the key has a value, False otherwise"""
        entry = self._data.get(key)
        return isinstance(entry, dict) and Data.KEY_DATA in entry

    def set_item(self, key, data) -> None:
        """Set the value of the item associated with key"""
        self._check_key(key)

        self._data[key][Data.KEY_DATA] = data
        self._data[key][Data.KEY_UPDATED] = True
        self._data[key][Data.KEY_LAST_UPDATED] = time.time()

        if key == "timezone":
            self._save()

    def get_item(self, key, default=None):
        """Get the value of the item associated with key, None if there is none"""
        try:
            return self._data[key][Data.KEY_DATA]
        except KeyError:
            return default

    def is_updated(self, key) -> bool:
        """True if the dirty flag for key is set"""
        try:
            return self._data[key][Data.KEY_UPDATED]
        except KeyError:
            return False

    def last_updated(self, key) -> int:
        """Return the time the key's value last changed"""
        try:
            return self._data[key][Data.KEY_LAST_UPDATED]
        except KeyError:
            return 0

    def age(self, key) -> int:
        """Return the age of the key's value"""
        return time.time() - self.last_updated(key)

    def clear_updated(self, key) -> None:
        """Clear the dirty flag for the key"""
        try:
            if not self._data[key][Data.KEY_UPDATED]:
                return
            self._data[key][Data.KEY_UPDATED] = False
        except KeyError:
            return

    def all(self) -> dict:
        """Returns the entire dictionary. Not really recommended, but used for debugging"""
        return self._data

    def _check_key(self, key) -> None:
        """
        Internal function that checks if a key exists and performs
        initialization if it doesn't
        """
        if key in self._data:
            return

        self._data[key] = {}
        self._data[key][Data.KEY_LAST_UPDATED] = 0
        self._data[key][Data.KEY_UPDATED] = False

    def _save(self) -> bool:
        """
        Attempt to save all current data to flash as a JSON file
        """
        try:
            storage.remount("/", False)
        except RuntimeError:
            return False

        gc.collect()

        try:
            with open(Data.SAVE_FILE, "w") as file:
                file.write(json.dumps(self._data))
        except OSError:
            return False
        finally:
            gc.collect()
            # always restore read-only mode, even if the write failed
            storage.remount("/", True)

        return True

    def _restore(self) -> bool:
        """
        Attempt to restore data from a JSON file stored in flash
        """
        try:
            with open(Data.SAVE_FILE, "r") as file:
                self._data = json.loads(file.read())
        except OSError:
            return False
        except ValueError:  # raised when the contents of the file are invalid JSON
            return False

        # Drop empty shells left by older code that created keys on read, and
        # clear dirty flags: they were whatever was in-flight when timezone
        # last triggered _save, and replaying them would re-show an old
        # message/greet once.
        for key in list(self._data.keys()):
            entry = self._data[key]
            if not isinstance(entry, dict) or Data.KEY_DATA not in entry:
                del self._data[key]
            else:
                entry[Data.KEY_UPDATED] = False

        return True
