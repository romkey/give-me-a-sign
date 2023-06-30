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

    def __init__(self):
        self._data = {}

    def has_item(self, key) -> bool:
        """True if the the key has a value, False otherwise"""
        return key in self._data

    def set_item(self, key, data) -> None:
        """Set the value of the item associated with key"""
        self._check_key(key)

        self._data[key]["data"] = data
        self._data[key]["updated"] = True
        self._data[key]["last_updated"] = time.monotonic()

    def get_item(self, key):
        """Get the value of the item associated with key, None if there is none"""
        self._check_key(key)

        try:
            return self._data[key]["data"]
        except KeyError:
            return None

    def is_updated(self, key) -> bool:
        """True if the dirty flag for key is set"""
        self._check_key(key)

        return self._data[key]["updated"]

    def last_updated(self, key) -> int:
        """Return the time the key's value last changed"""
        self._check_key(key)
        return self._data[key]["last_updated"]

    def age(self, key) -> int:
        """Return the age of the key's value"""
        return time.time() - self.last_updated(key)

    def clear_updated(self, key) -> None:
        """Clear the dirty flag for the key"""
        self._check_key(key)

        self._data[key]["updated"] = False

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
        self._data[key]["last_updated"] = 0
        self._data[key]["updated"] = False

    def _save(self) -> None:
        """
        Attempt to save all current data to flash as a JSON file
        """
        storage.remount("/", False)
        with open("/data.json", "w") as file:
            file.write(json.dumps(self._data))

        print("saved!")

        storage.remount("/", True)

    def _restore(self) -> None:
        """
        Attempt to restore data from a JSON file stored in flash
        """
        with open("/data.json", "w") as file:
            self._data = json.loads(file.read())
