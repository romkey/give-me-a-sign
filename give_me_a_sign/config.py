# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/config - rotation and module configuration
=========================================================

* Author: John Romkey
"""

import json

CONFIG_FILE = "/config.json"

DEFAULT_ROTATION = [
    {"module": "clock", "duration": 20},
    {"module": "weather", "duration": 10},
    {"module": "aqi", "duration": 10},
    {"module": "uv", "duration": 10},
    {"module": "pollen", "duration": 10},
]


def load_config(logger=None):
    """
    Load /config.json from CIRCUITPY.

    Returns a dict with keys "modules" (extra import names) and "rotation"
    (ordered screen list). On any failure, returns defaults.
    """
    config = {"modules": [], "rotation": _default_rotation()}
    try:
        with open(CONFIG_FILE, "r") as file:
            data = json.loads(file.read())
    except OSError:
        return config
    except ValueError as error:
        if logger is not None:
            logger.error(f"config: invalid JSON: {error}")
        return config

    if not isinstance(data, dict):
        if logger is not None:
            logger.error("config: root must be an object")
        return config

    modules = data.get("modules", [])
    if isinstance(modules, list):
        config["modules"] = [str(name) for name in modules if name]

    rotation = data.get("rotation")
    if isinstance(rotation, list) and rotation:
        parsed = []
        for entry in rotation:
            screen = _parse_rotation_entry(entry, logger)
            if screen is not None:
                parsed.append(screen)
        if parsed:
            config["rotation"] = parsed

    return config


def _default_rotation():
    parsed = []
    for entry in DEFAULT_ROTATION:
        screen = _parse_rotation_entry(entry, None)
        if screen is not None:
            parsed.append(screen)
    return parsed


def _parse_rotation_entry(entry, logger):
    if not isinstance(entry, dict):
        return None

    if "screen" in entry:
        screen = entry["screen"]
        if not isinstance(screen, dict):
            return None
        duration = _parse_duration(screen.get("duration"), 10)
        complications = screen.get("complications", [])
        if not isinstance(complications, list):
            complications = []
        parsed_complications = []
        for comp in complications:
            if not isinstance(comp, dict):
                continue
            ref = comp.get("ref")
            if not ref:
                continue
            try:
                x = int(comp.get("x", 0))
                y = int(comp.get("y", 0))
            except (TypeError, ValueError):
                continue
            parsed_complications.append({"ref": str(ref), "x": x, "y": y})
        if not parsed_complications:
            if logger is not None:
                logger.error("config: composed screen has no complications")
            return None
        return {
            "type": "composed",
            "name": str(screen.get("name", "composed")),
            "duration": duration,
            "complications": parsed_complications,
        }

    module = entry.get("module")
    if not module:
        return None
    duration = _parse_duration(entry.get("duration"), None)
    return {
        "type": "module",
        "module": str(module),
        "duration": duration,
    }


def _parse_duration(value, default):
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
