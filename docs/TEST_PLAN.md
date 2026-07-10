<!--
SPDX-FileCopyrightText: 2023-2026 John Romkey

SPDX-License-Identifier: MIT
-->

# Give Me A Sign — Test Plan

This document describes how to test Give Me A Sign, an MQTT-driven LED matrix
sign running CircuitPython 10.x+ on a native-WiFi board (primarily the
Adafruit Matrix Portal S3 driving a 64x32 HUB75 panel).

The sign has no HTTP API. All data and commands arrive over MQTT, and the
sign publishes its own state (availability, display state, diagnostics) back
to the broker, so most functional tests are "publish a payload, verify the
display and/or the sign's published topics."

## 1. Scope and Test Levels

| Level | What | Where it runs | Automation |
|-------|------|---------------|------------|
| 1 | Host unit tests | pytest on CPython, in CI | Fully automated |
| 2 | MQTT integration tests | Host + broker + real sign | Scripted publishes, mostly visual verification |
| 3 | Manual on-device tests | Real sign | Manual |
| 4 | Home Assistant integration | HA + broker + real sign | Manual |

### Level 1 — Host unit tests (pytest, CI-runnable)

The only current test is `tests/test_smoke.py` (`assert True`). CI
(`.github/workflows/build.yml`) runs pre-commit, pytest, and a bundle build.

Most modules import `board`, `displayio`, `pwmio`, `wifi`, or `rtc` at module
level, so they cannot be imported under host CPython directly. Two paths to
real unit coverage:

- **Directly testable today** (no hardware imports, or trivially isolated):
  - `give_me_a_sign/data.py` — imports only `time`, `gc`, `json`, `storage`.
    `storage` needs a stub (it is only used in `_save`/`_restore`).
  - `give_me_a_sign/mqtt.py` static helpers — `SignMQTT._decode_mqtt_payload`
    and the plain-text fallback logic in `store_data` (needs light stubbing).
  - Pure static methods: `Weather._image_stem`, `Weather._temp_color`,
    `Weather._forecast_text`, `AQI._aqi_color`.
- **Testable with a `board`/`displayio`/`terminalio` stub package** (add a
  `tests/stubs/` directory on `sys.path` in `conftest.py`): timezone and
  solar logic in `clock.py`, greet anonymization in `greet.py`, tone payload
  validation in `tones.py`.

Recommended unit test cases:

**`Data` store (`tests/test_data.py`)**

- `set_item`/`get_item` round trip; `get_item` of missing key returns the
  default (`None` unless given).
- `is_updated` is `True` after `set_item`, `False` after `clear_updated`,
  and `False` for a key never set.
- `clear_updated` on a missing key does not raise.
- `age`/`last_updated`: a never-set key reports `last_updated == 0`; a set
  key's age tracks `time.time()`.
- Setting key `timezone` triggers `_save`; other keys do not (stub `storage`
  and assert on remount/open calls).
- `_restore` with invalid JSON or a missing file returns `False` and leaves
  the store empty; `_restore` drops entries without a `data` field and
  clears all dirty flags (a persisted message/greet must not replay after
  reboot).

**MQTT payload handling (`tests/test_store_data.py`)**

- Valid JSON object payloads are stored under the endpoint key.
- Plain-text (non-JSON) payload to `message` becomes `{"text": ...}`;
  to `greet` becomes `{"person": ...}` (Home Assistant text entities send
  plain text).
- A JSON *string* payload (e.g. `"hello"`) to `message`/`greet` is also
  wrapped, since `json.loads` succeeds but the result is not a dict.
- Malformed JSON to any other endpoint is logged and *not* stored (no crash).
- `_decode_mqtt_payload` handles `bytes`, `memoryview`, and `str` inputs.

**Weather helpers (`tests/test_weather_helpers.py`)**

- `_image_stem`: `icon` field wins (`"10d"` → `10d`, `"01n"` preserved);
  `condition_id` maps via `OWM_ID_TO_ICON` (e.g. `500` → `10d`,
  `800` → `01d`); numeric `conditions` (int, float, digit string) treated as
  condition id; legacy names normalize (`"Partly Cloudy"` → `02d`); unknown
  string falls through as a literal stem; no usable fields → `50d`.
- `_temp_color` boundaries: 49 → blue, 50–69 → teal, 70–79 → green,
  80–89 → orange, 90+ → red.
- `_forecast_text`: with `{"low": 55, "high": 79}` → `"45% 55->79"`; with
  missing/invalid forecast → `"45%"` (humidity only).

**AQI color thresholds (`tests/test_aqi_color.py`)**

- `_aqi_color` boundaries: 50/51, 100/101, 150/151, 200/201, 300/301
  produce green, yellow, orange, red, purple, maroon respectively.

**Clock timezone and solar logic (`tests/test_clock.py`, needs stubs)**

- `_check_timezone_offset` selects the offset of the latest transition with
  `timestamp <= now` and caches until the next future transition.
- A freshly updated timezone table invalidates the cache immediately.
- Empty `transitions` list and missing keys are handled without crashing.
- `_calculate_color`: no solar data → `NO_SOLAR_COLOR` (0xFFAA00); missing
  `sunrise`/`sunset` keys → `NO_SOLAR_COLOR`; day/night/pre-sunrise/
  pre-sunset windows for normal ordering; the Home-Assistant-style
  `sunrise > sunset` (next-event) ordering still yields day color during the
  day; `morning_after_roll` suppresses stale pre-dawn blue after sunrise
  rolls forward.
- `is_sundown`: `True` within 30 minutes before sunset and at night with
  normal ordering; `False` with HA next-event ordering during the day;
  `False` with no solar data.

**Greet anonymization (`tests/test_greet.py`, needs stubs)**

- A person listed in `anonymous_greetings` (comma-separated env var) renders
  as "Hi totally / human being"; anyone else as "Welcome / {first name}".
- Missing `person` key, non-dict data, or non-string person → `show()`
  returns `False`.

**Tones validation (`tests/test_tones.py`, needs `pwmio`/`board` stubs)**

- Valid tone list normalizes to `(int, float, float)` tuples, including
  numeric strings.
- Missing `tones` key, non-list, or a tone with a bad field → `play()`
  returns `False` and does not modify playback state.

### Level 2 — MQTT integration tests (host → broker → sign)

Scripted publishes with `mosquitto_pub`, observed on the physical display
and via the sign's published topics with `mosquitto_sub`. These replace the
deleted curl-based `tests/*.sh` scripts (see section 6).

### Level 3 — Manual on-device tests

Buttons, RTC detection, boot behavior, crash recovery. See section 5.

### Level 4 — Home Assistant integration

MQTT autodiscovery entities: display switch, device-time datetime, reboot and
publish-data buttons, greet/message text entities, diagnostics sensors,
availability. See section 5.

## 2. Test Environment Setup

**Hardware**

- Adafruit Matrix Portal S3 with a 64x32 RGB LED matrix (optionally a
  chained/tiled larger display to exercise canvas scaling).
- Optional: DS3231 or PCF8523 RTC breakout on I2C; piezo buzzer on pin A4.
- USB connection to a host for the serial console (all errors and MQTT
  activity are printed there).

**Software**

- CircuitPython 10.x+ (10.2+ to exercise `supervisor.get_setting()`;
  earlier 10.x exercises the `os.getenv()` fallback).
- Libraries from `requirements.txt` installed with `circup`.
- An MQTT broker reachable from the sign (Mosquitto is fine), and
  `mosquitto_pub`/`mosquitto_sub` on the test host.

**Configuration** — `settings.toml` on CIRCUITPY per
`examples/settings.toml`: `wifi_ssid`/`wifi_password` (or
`CIRCUITPY_WIFI_*`), `MQTT_BROKER`, `MQTT_PORT`, `MQTT_SSL`,
`MQTT_USERNAME`/`MQTT_PASSWORD`, `MQTT_TOPIC_PREFIX` (default
`givemeasign`), and `anonymous_greetings` for the greet tests.

**Finding the sign's topics** — per-device topics embed the WiFi MAC address
with `:` replaced by `_`. Easiest way to discover it:

```bash
mosquitto_sub -h $BROKER -v -t 'givemeasign/sign/+/available'
```

The topic that reports `online` gives you the device id. For the rest of
this document:

```bash
export BROKER=your-broker
export PREFIX=givemeasign
export SIGN=$PREFIX/sign/aa_bb_cc_dd_ee_ff   # substitute your MAC
```

Broadcast topics (`$PREFIX/all/module/{endpoint}`) and per-device topics
(`$SIGN/module/{endpoint}`) are interchangeable for data delivery; test at
least one endpoint on each form.

## 3. MQTT Integration Test Cases (per module)

General expectations that apply to every data endpoint:

- The serial console logs `mqtt store_data! {key} {payload}` on receipt.
- Malformed JSON (to any endpoint except `message`/`greet`) logs
  `server:store_data({key}) store_data failed` and the sign keeps running.
- Interrupt-style modules (`greet`, `message`, `image`, `tones`) act on the
  *dirty flag*, so they trigger once per publish. Rotation modules
  (`weather`, `aqi`, `uv`, `pollen`) display on their turn in the cycle:
  CLOCK (20s) → WEATHER (10s) → AQI (10s) → UVI (10s) → POLLEN (10s) → repeat.
- Rotation screens are skipped when their data is older than 1 hour or
  `show()` fails — verify a screen drops out of rotation ~1 hour after its
  last update.

### 3.1 message

```bash
mosquitto_pub -h $BROKER -t $PREFIX/all/module/message \
  -m '{"text": "hello world", "color": 65280, "duration": 5}'
```

| Case | Payload | Expected |
|------|---------|----------|
| Basic | `{"text": "hi", "color": 16711680}` | Red "hi", centered, shown 15 s (default), then back to clock |
| Duration | add `"duration": 5` | Shown ~5 s |
| Invalid duration | `"duration": 0` or `"duration": "x"` | Falls back to 15 s |
| No color | `{"text": "hi"}` | White text (default 0xFFFFFF) |
| Plain text | `-m 'just text'` (not JSON) | Wrapped as `{"text": "just text"}`, white, 15 s |
| Wide text | text wider than 64 px | Left-aligned at x=0, not centered (no scrolling) |
| Bad data | `{"nope": 1}` | `show()` fails; serial logs "message: bad data"; sign continues rotation |

### 3.2 greet

| Case | Payload | Expected |
|------|---------|----------|
| Basic | `{"person": "John R.", "door": "front"}` | "Welcome" / "John" (first name only), 15 s |
| Anonymous | person listed in `anonymous_greetings` | "Hi totally" / "human being" |
| Plain text | `-m 'Jane D.'` | Wrapped as `{"person": "Jane D."}` and greeted |
| Bad data | `{"door": "front"}` (no person) | Nothing shown, rotation continues |
| Non-string person | `{"person": 5}` | Nothing shown |

### 3.3 weather and forecast (two separate topics)

```bash
mosquitto_pub -h $BROKER -t $PREFIX/all/module/weather \
  -m '{"current": {"temperature": 75, "humidity": 45, "icon": "10d", "condition_id": 500}}'
mosquitto_pub -h $BROKER -t $PREFIX/all/module/forecast \
  -m '{"low": 55, "high": 79}'
```

Note: forecast is its own endpoint. Embedding a `forecast` key inside the
weather payload (as the old HTTP test did) will *not* populate the forecast
line.

| Case | Payload | Expected |
|------|---------|----------|
| Full | current + forecast above | Rain icon, "75" in green, "45% 55->79" bottom line |
| No forecast | weather only, forecast never sent | Bottom line shows just "45%" |
| Icon priority | `"icon": "01n"` with `"condition_id": 800` | Night-clear icon (01n), not day (01d) |
| Condition id only | `{"current": {"temperature": 75, "humidity": 45, "condition_id": 200}}` | Thunderstorm icon (11d) |
| Legacy name | `"conditions": "partlycloudy"` (no icon/id) | 02d icon |
| Unknown icon | `"conditions": "nosuchthing"` | Icon load fails (serial: "file not found"), temp + humidity still shown |
| Temp colors | temperature 45 / 65 / 75 / 85 / 95 | blue / teal / green / orange / red |
| Missing temperature or humidity | omit either | Weather screen skipped in rotation |
| Staleness | wait > 1 h after last publish | Weather screen drops out of rotation |

### 3.4 aqi

Payload key is `aqi` (not `index`): `{"aqi": 42}`.

| Case | Payload | Expected |
|------|---------|----------|
| Value + color | `{"aqi": 42}` / 75 / 125 / 175 / 250 / 350 | "AQI n" in green / yellow / orange / red / purple / maroon, mini-clock top-right |
| Bad data | `{"index": 42}` or `{"aqi": "x"}` | AQI screen skipped |

### 3.5 uv

Payload key is `index`: `{"index": 4.5}`.

| Case | Payload | Expected |
|------|---------|----------|
| Basic | `{"index": 4.56}` | "UVI 4.5" (one decimal) in purple, mini-clock |
| Zero | `{"index": 0}` | UVI screen skipped (treated as nothing to show) |
| Sundown | valid UV data while `is_sundown` is true | UVI screen skipped entirely |
| Bad data | `{"uv": 4}` | Skipped |

### 3.6 pollen

| Case | Payload | Expected |
|------|---------|----------|
| Basic | `{"pollen": 7}` | Pollen screen with value and mini-clock |
| Bad data | missing/invalid `pollen` key | Skipped |

### 3.7 solar (clock colors and sundown behavior)

Payload: `{"sunrise": <unix UTC>, "sunset": <unix UTC>}`.

Prefer choosing sunrise/sunset relative to real time. Optionally override
the clock first via `$SIGN/time/set` (section 3.14) if you need absolute
control:

| Case | Sunrise/sunset relative to now | Expected clock color |
|------|-------------------------------|----------------------|
| Day | sunrise 4 h ago, sunset 4 h ahead | Green |
| Pre-sunset | sunset 30 min ahead | Orange; also `is_sundown` true, so UVI skipped |
| Night | sunset 2 h ago, sunrise 10 h ahead | Red |
| Pre-sunrise | sunrise 30 min ahead | Blue |
| HA next-event ordering | sunset later today, sunrise tomorrow (sunrise > sunset) | Green during the day, not red |
| No solar data | never published (or after reboot with no retained data) | Amber/no-solar color (0xFFAA00) |
| Bad data | `{"sunrise": 123}` (missing sunset) | Amber, error logged |

### 3.8 timezone

Payload from `extras/timezones/tz.rb`:
`{"timezone": "America/Los_Angeles", "transitions": [{"timestamp": ..., "offset": ...}, ...]}`.

| Case | Expected |
|------|----------|
| Publish table for local zone | Clock shows correct local time within ~1 s |
| Persistence | Reboot the sign with the broker offline: local time is still correct (table restored from `/data.json` on flash) |
| Cache invalidation | Publish a table with a deliberately wrong offset, confirm the clock shifts immediately, then publish the correct one — it must correct without a reboot |
| DST transition | Table with a transition timestamp ~2 minutes in the future: offset changes when the timestamp passes |
| Empty transitions | `{"transitions": []}` — no crash, offset unchanged |

### 3.9 tones

```bash
mosquitto_pub -h $BROKER -t $PREFIX/all/module/tones \
  -m '{"tones": [{"frequency": 440, "duration": 0.5, "volume": 100}, {"frequency": 880, "duration": 0.5, "volume": 50}]}'
```

| Case | Expected |
|------|----------|
| Basic sequence | Tones play immediately in order, at proportional volumes, then the buzzer goes silent (duty cycle off) |
| Display unaffected | Tones play without interrupting whatever screen is showing |
| String numerics | `"frequency": "440"` still plays |
| Bad data | missing `tones`, or a tone with a bad field | Nothing plays, serial logs "tones: bad data", buzzer not left stuck on |

### 3.10 image

| Case | Payload | Expected |
|------|---------|----------|
| Canvas-sized | `{"filename": "/gimas/assets/nyan-16.bmp"}` (or any BMP ≤ 64x32 on CIRCUITPY) | Centered, scaled with the canvas, 15 s (or `duration`) |
| Oversized image | BMP larger than 64x32 on a large display | Shown unscaled, centered on the physical display |
| Missing file | `{"filename": "/nope.bmp"}` | Nothing shown, rotation continues |
| Bad data | `{"filename": null}` or `{}` | Nothing shown |

### 3.11 reboot

```bash
mosquitto_pub -h $BROKER -t $SIGN/reboot -m 'x'
```

Expected: immediate `microcontroller.reset()`; the LWT publishes retained
`offline` on `$SIGN/available`, then the sign reboots, reconnects, and
publishes `online`.

### 3.12 display on/off

```bash
mosquitto_pub -h $BROKER -t $SIGN/display/set -m 'OFF'
```

| Case | Expected |
|------|----------|
| OFF | Matrix goes black; retained `OFF` published on `$SIGN/display/state` |
| ON | Content returns; retained `ON` on state topic |
| Case-insensitive | `on` / `off` work |
| Unknown payload | `maybe` — ignored, no state change, no state publish |
| While off | Publish a message while display is off: display stays black (state machine still runs underneath) |
| After reboot | Display state resets to ON (state is not persisted) |

### 3.13 Published topics (observe with `mosquitto_sub -v -t "$SIGN/#"`)

| Topic | Expected |
|-------|----------|
| `$SIGN/available` | Retained `online` after connect; retained `offline` via LWT after power-off or ungraceful disconnect |
| `$SIGN/display/state` | Retained `ON`/`OFF`, updated on every switch command |
| `$SIGN/time/state` | Retained ISO 8601 UTC datetime; updated on connect, after `time/set`, and with diagnostics (~60 s) |
| `$SIGN/data/state` | Retained full Data store JSON after `data/publish` |
| `$SIGN/diagnostics` | JSON roughly every 60 s: uptime, time_utc, timezone_offset, free_memory, flash_free/size, rtc type (`software`/`DS3231`/`PCF8523`), wifi ssid/bssid/rssi, mac, IPv4, CircuitPython version, board id, display dimensions. Sanity-check values against reality |
| `homeassistant/.../config` | Autodiscovery configs for the switch, datetime, buttons, text entities, and sensors |

### 3.14 time/set

```bash
mosquitto_pub -h $BROKER -t $SIGN/time/set -m '2026-07-10T12:00:00+00:00'
mosquitto_pub -h $BROKER -t $SIGN/time/set -m '{"epoch": 1700000000}'
mosquitto_pub -h $BROKER -t $SIGN/time/set -m '1700000000'
```

| Case | Expected |
|------|----------|
| ISO 8601 UTC | RTC updates; retained ISO string on `$SIGN/time/state`; clock display jumps |
| Epoch / JSON epoch | Same as ISO |
| Bad payload | Ignored; serial logs error; state topic unchanged |
| HA datetime entity | Setting **Device Time** in HA publishes ISO UTC to `time/set` |

### 3.15 data/publish

```bash
mosquitto_pub -h $BROKER -t $SIGN/data/publish -m publish
mosquitto_sub -h $BROKER -t $SIGN/data/state -C 1
```

| Case | Expected |
|------|----------|
| After storing data | Retained JSON on `$SIGN/data/state` includes recently published keys (`aqi`, `message`, …) with `data` / `updated` / `last_updated` |
| HA button | **Publish Data Store** triggers the same dump |
| Empty store | Valid JSON object (possibly `{}` or only persisted timezone) |

### 3.16 Store-only endpoints

`lunar`, `debug`, and `trimet` accept and store payloads but have no display
module wired into the rotation (`trimet.py` is a stub). Test only that
publishing to them does not crash the sign; they show up in nothing.

## 4. Resilience and Negative Tests

| ID | Scenario | Procedure | Expected |
|----|----------|-----------|----------|
| R1 | WiFi drop | Take the AP down (or block the sign's MAC) while running | Serial shows reconnect attempts with backoff doubling 5 s → 90 s cap; clock keeps updating from the RTC throughout; the display never freezes |
| R2 | WiFi restore | Bring the AP back | WiFi reconnects, serial logs "WiFi restored, rebuilding MQTT client", MQTT reconnects with a fresh socket pool, `available` returns to `online` |
| R3 | Broker down | Stop the broker, leave WiFi up | MQTT retry with backoff 5 s → 120 s cap; display unaffected; each connect attempt bounded (~0.25 s socket timeout), no multi-second stalls |
| R4 | Broker restored | Restart the broker before 20 failures | Reconnects, re-subscribes, republishes online status and display state |
| R5 | Reset after repeated failure | Leave the broker down long enough for 20 consecutive failures | Serial logs "MQTT: too many consecutive failures, resetting MCU" and the sign resets (by design) |
| R6 | Boot with no WiFi | Power on with the AP down | Boot completes to the clock (amber, wrong time until NTP); no crash; recovers fully when the AP appears |
| R7 | Boot with no broker | Power on with WiFi up, broker down | Same: boot completes, retries in the background |
| R8 | NTP unavailable | Block UDP 123, reboot | `ntp_sync` returns None, retry every 5 min; with a hardware RTC the time is still correct; without one the clock runs from the software RTC epoch |
| R9 | NTP time jump | Let NTP correct a badly wrong RTC | Screen rotation timing unaffected (countdowns use `time.monotonic_ns()`, not wall time) |
| R10 | Retained messages on reboot | Publish a retained message (`-r`), reboot the sign | The retained payload is re-delivered and the message shows once after boot — confirm this matches expectations, and that `/data.json` restore itself never replays an old message (dirty flags cleared on restore) |
| R11 | Low memory | Long soak (24 h+) with periodic publishes on all endpoints | `free_memory` in diagnostics stays stable (no leak trend); if it drops below 10 kB the sign logs "low memory" at most every 30 s and keeps running |
| R12 | Crash recovery | Introduce a deliberate exception (temporarily) | `examples/code.py` catches it, waits 30 s, and resets the MCU rather than dying to the REPL |
| R13 | Garbage on every topic | Publish random bytes to every subscribed topic | Errors logged, nothing crashes, rotation continues |
| R14 | CircuitPython version gate | Boot the package on CircuitPython 9.x | `RuntimeError` at import with a clear version message |

**Manual on-device checks (Level 3)**

| ID | Action | Expected |
|----|--------|----------|
| M1 | Short-press UP | Scrolling IP address for 10 s, then clock |
| M2 | Short-press DOWN | Nyan cat splash for 10 s, then clock |
| M3 | Long-press UP | "halted" in red; sign halts until power cycle |
| M4 | Long-press DOWN | "restart" in red for 2 s, then MCU reset |
| M5 | Boot splash | WiFi splash image shows during connect |
| M6 | RTC detection | With DS3231 / PCF8523 / no RTC attached, serial and diagnostics report the right RTC type |
| M7 | Canvas scaling | On a display larger than 64x32 (e.g. 128x64), content is integer-scaled and centered; on 128x32, scaled x1 and letterboxed horizontally |

## 5. Home Assistant Integration Tests (Level 4)

With HA connected to the same broker and MQTT autodiscovery enabled:

| ID | Check | Expected |
|----|-------|----------|
| HA1 | Device appears | One device (named per `SIGN_NAME` if set) with switch, datetime, buttons, text, and sensor entities |
| HA2 | Display switch | Toggling in HA blanks/restores the matrix; state stays in sync both ways (including when toggled via raw MQTT) |
| HA3 | Reboot button | Pressing it resets the sign |
| HA4 | Message text entity | Typing plain text shows it on the sign (plain-text fallback path) |
| HA5 | Greet text entity | Typing a name greets them |
| HA6 | Diagnostics sensors | Uptime, RSSI, free memory, etc. update roughly every minute |
| HA7 | Availability | Powering the sign off marks the device unavailable in HA (LWT); powering on restores it |
| HA8 | HA restart | Restart HA; entities come back (discovery configs retained or re-advertised) |
| HA9 | Device Time | Setting the datetime entity updates the sign clock; state reflects the new time |
| HA10 | Publish Data Store | Pressing the button publishes full store JSON to `$SIGN/data/state` |

## 6. Regression Traceability — old HTTP tests → MQTT

The deleted `tests/*.sh` scripts exercised the removed HTTP API. Equivalent
MQTT coverage:

| Deleted script | Old behavior | Replacement |
|----------------|--------------|-------------|
| `test_message.sh` | POST `/message` | Section 3.1 |
| `test_greet.sh` | POST `/greet` (named + anonymous) | Section 3.2 |
| `test_weather.sh` | POST `/weather` with conditions variants | Section 3.3 — note forecast moved to its own topic |
| `test_aqi.sh` | POST `/aqi` | Section 3.4 |
| `test_uv.sh` | POST `/uv` | Section 3.5 |
| `test_tones.sh` | POST `/tones` | Section 3.9 |
| `test_times.sh` | POST `/set-time` + `/solar` to step through color phases | Sections 3.7 and 3.14 (`time/set` + relative solar timestamps) |
| `test_timezone_offsets.sh` | POST `/timezone` from a JSON file | Section 3.8 |
| `test_reset.sh` | GET `/reboot` | Section 3.11 |
| `test_info.sh` | GET `/info` device info | Covered by the `diagnostics` topic (3.13) |
| `test_data.sh` | GET `/data` full store dump | Section 3.15 (`data/publish` → `data/state`) |

Recommended follow-up (out of scope for this document): recreate the
scripts as `tests/mqtt/test_*.sh` wrappers around `mosquitto_pub`, driven by
`BROKER`/`PREFIX`/`SIGN` environment variables, so the Level 2 suite can be
run in one pass against a bench sign.

## 7. CI Recommendations

What `.github/workflows/build.yml` can realistically automate:

- **Keep**: pre-commit (lint/format), bundle build via
  `circuitpython-build-bundles` (this is the de facto "does it package"
  check).
- **Add**: the Level 1 pytest suite from section 1, with a `tests/stubs/`
  package providing minimal `board`, `displayio`, `terminalio`, `pwmio`,
  `storage`, `rtc`, `wifi`, and `microcontroller` fakes. This runs on plain
  CPython in the existing pytest step — no workflow changes needed beyond
  adding the tests.
- **Optionally add**: a broker-only integration smoke test — spin up
  Mosquitto in a service container and run the `store_data` logic against a
  real client library on CPython. Marginal value over the unit tests; do it
  only if the MQTT glue starts regressing.
- **Cannot automate in GitHub Actions**: anything requiring the display,
  buttons, buzzer, WiFi, or real CircuitPython (Levels 2–4). These need a
  bench sign; run the Level 2 script suite and the section 4/5 checklists
  manually before tagging a release.

Suggested release gate: CI green (lint + unit + bundle), Level 2 script
suite passed on hardware, plus a 24-hour soak (R11) with diagnostics
monitored for memory trend.
