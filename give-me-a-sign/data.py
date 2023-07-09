# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/data - data storage for LED Matrix display
====================================================

* Author: John Romkey
"""

import time
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
        return key in self._data

    def set_item(self, key, data) -> None:
        """Set the value of the item associated with key"""
        self._check_key(key)

        self._data[key][Data.KEY_DATA] = data
        self._data[key][Data.KEY_UPDATED] = True
        self._data[key][Data.KEY_LAST_UPDATED] = time.time()

        self._save()

    def get_item(self, key):
        """Get the value of the item associated with key, None if there is none"""
        self._check_key(key)

        try:
            return self._data[key][Data.KEY_DATA]
        except KeyError:
            return None

    def is_updated(self, key) -> bool:
        """True if the dirty flag for key is set"""
        self._check_key(key)

        return self._data[key][Data.KEY_UPDATED]

    def last_updated(self, key) -> int:
        """Return the time the key's value last changed"""
        self._check_key(key)
        return self._data[key][Data.KEY_LAST_UPDATED]

    def age(self, key) -> int:
        """Return the age of the key's value"""
        return time.time() - self.last_updated(key)

    def clear_updated(self, key) -> None:
        """Clear the dirty flag for the key"""
        self._check_key(key)

        self._data[key][Data.KEY_UPDATED] = False
        self._save()

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

        with open(Data.SAVE_FILE, "w") as file:
            file.write(json.dumps(self._data))

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

        return True
