<!--
SPDX-FileCopyrightText: 2023-2026 John Romkey

SPDX-License-Identifier: MIT
-->

# Give Me A Sign!

Give Me A Sign! is an info sign designed for hacker and makerspaces,
although you could use it in your home or office as well.

![clock](images/clock.jpg) ![weather](images/weather-display.jpg)
![Air Quality Index](images/aqi-display.jpg) ![UV Index](images/uvi-display.jpg)

The sign will mostly look like a clock, while sometimes displaying
other useful information like messages, weather, air quality
information or whatever you push to it.

The sign is intended to be deployed and left aone. It doesn't pull
data (other than syncing its clock via NTP), data gets pushed to
it. The project includes examples of how to set up Home Assistant to
push data to the sign.

## Design Philosophy

In the age of connected devices one of the big questions becomes
"where should we do what?". For instance, should a smart sign that
shows the weather fetch the weather information itself, or would it be
better to push that information to it from a more capable computer?

Two important questions arise:

1. Is the device intended to be stand-alone, with no additional
   support? If so then obviously the complexity has to be in the
   device.
2. If the device is not intended to be stand-alone then where is the
   most appropriate place to put different functions?

Give Me A Sign! is not intended to run stand-alone. Its clock function
can but the biggest design decision here is to use an external source
(or sources) to push information to the sign rather than have it pull
information.

This allows much greater flexibility. For instance, PDX Hackerspace
has its own weather station. Rather than use weather conditions from a
weather service, we can use the ones that our weather station
reports. We still need weather forecasts, though, and we it's
convenient to pull the "current conditions" (like rain, snow,
volcanos, etc)  from an external source.

Pushing the data allows us to easily adapt to a mix of local and
remote sources and change that as we wish without having to update the
signs distributed around the space.

There are also questions about security. While it's difficult to
correctly protect secrets and sensitive information like passwords and
API keys on capable systems like Linux, it's even more difficult or
even impossible to protect them on embedded devices, especially
devices that people have physical access to. Not having them there at
all also means that you don't have to update certificates, change API
keys or keep other credentials up to date on devices where it's
inherently more difficult to do so.

## Hardware

This code targets boards with **native WiFi** and enough RAM for the full
application, such as the [Adafruit Matrix Portal
S3](https://www.adafruit.com/product/5778) connected to a 64x32 LED matrix.
The older Matrix Portal M4 (SAMD51 + AirLift ESP32 co-processor) is no longer
supported — there is not enough RAM to run the sign reliably.

Other native-WiFi matrix setups may work but have not been tested.

### Larger displays

Displays built from multiples of the standard 64x32 panel are supported:
chain panels for more width, stack ("tile") them for more height, or use
64-row panels (which need the ADDR E jumper closed and a board that
provides the fifth address line, like the MatrixPortal S3). Configure the
geometry in `settings.toml`:

```toml
MATRIX_WIDTH = 128         # total pixels across (chained panels)
MATRIX_PANEL_HEIGHT = 32   # rows per panel: 32, or 64 (needs ADDR E)
MATRIX_TILE = 2            # rows of panels stacked vertically
MATRIX_SERPENTINE = true   # alternate panel rows rotated 180 degrees
MATRIX_BIT_DEPTH = 2       # color depth; higher uses more RAM/CPU
```

Content is laid out on a virtual 64x32 canvas and integer-scaled to fit
the display, centered. Sizes that aren't proportional to 64x32 (say
128x32) scale by the common factor and letterbox the rest. Images pushed
to the `image` module via MQTT that are larger than 64x32 are shown unscaled at
the display's native resolution.

## Software

This project is written in CircuitPython. It depends on several
libraries that help manage the LED matrix, WiFi, the buttons, and the
RTC modules.

The application ships as a CircuitPython **library package** named
`give_me_a_sign` (import `GiveMeASign` from it). The package loads the
other modules, connects to MQTT, and drives the main display loop.
Fonts, splash images, and weather BMPs live in **`give_me_a_sign/assets/`**
(next to the `.py` files under `/lib/give_me_a_sign/` on the device).

Install the library on `CIRCUITPY` under `lib/give_me_a_sign/` using
[CircUp](https://learn.adafruit.com/keep-your-circuitpython-libraries-on-devices-up-to-date-with-circup/install-command)
(Adafruit’s recommended tool), for example from a clone of this repo:

```bash
circup install -r requirements.txt ./give_me_a_sign --py
```

CircUp reads `requirements.txt` for bundle library names and copies the
local `give_me_a_sign` package; use `--upgrade` if copies already exist on
the device. Bundle entries use **import names** (for example
`adafruit_minimqtt`, `adafruit_ntp`) as in
[the CircuitPython library bundle](https://circuitpython.org/libraries).

### Development vs release installs

For local development, install the package as `.py` so code remains readable on
the device:

```bash
circup install -r requirements.txt ./give_me_a_sign --py --upgrade
```

On every push and pull request, Build CI runs `circuitpython-build-bundles` and
uploads a `bundles` artifact with:

- `give-me-a-sign-10.x-mpy-*.zip` (and 9.x) — precompiled `.mpy` under `lib/`
- `give-me-a-sign-py-*.zip` — source `.py` under `lib/`
- examples and metadata JSON

Download those from the Actions run’s Artifacts section. For public distribution,
publish a GitHub Release with a SemVer tag (for example `0.5.2`). Release CI
rebuilds the same zips and attaches them to the release; build tools stamp
`__version__` from that tag.

### CircuitPython Community Bundle

This repo follows the
[CircuitPython Community Bundle](https://github.com/adafruit/CircuitPython_Community_Bundle)
library layout and CI (`circuitpython-build-tools`). To get into the bundle:

1. Land a SemVer-tagged GitHub Release (for example `0.5.2`) so release assets
   include stamped `.mpy` zips.
2. Fork `adafruit/CircuitPython_Community_Bundle`, add this repo as a submodule
   under `libraries/helpers/give_me_a_sign` (or another fitting category), and
   update `circuitpython_community_library_list.md`.
3. Open a PR against the Community Bundle. After merge, daily bundle releases
   pick up new tags from this repo automatically.

See Adafruit’s guide:
[Sharing in the Community Bundle](https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-in-the-community-bundle).

## Preparing The Sign

### Update CircuitPython

Install the latest CircuitPython for your board, for example:

https://circuitpython.org/board/adafruit_matrixportal_s3/

## Mounting

\#4-40 3/8" screws


## Installation

1. Install CircuitPython on the board and mount `CIRCUITPY`.
2. Install libraries: from this repo run `circup install -r requirements-circuitpython.txt ./give_me_a_sign --py --upgrade` so bundle dependencies and the `give_me_a_sign` package are copied to `lib/`.
3. Copy `examples/code.py` to the root of `CIRCUITPY` (or merge into your own `code.py`), and add `settings.toml` / environment as needed.

## API

Data is pushed to the sign over **MQTT**, not HTTP. Each sign subscribes to
topics under `MQTT_TOPIC_PREFIX` (default `givemeasign`):

- `{prefix}/all/module/{endpoint}` — broadcast to every sign
- `{prefix}/sign/{mac}/module/{endpoint}` — per-device (used by Home Assistant)

Supported `{endpoint}` values include `weather`, `message`, `greet`, `aqi`, `uv`,
`pollen`, `forecast`, `lunar`, `tones`, `image`, `timezone`, `solar`, `trimet`,
and `debug`. Payloads are JSON objects (plain text is accepted for `message` and
`greet`).

Per-device command topics (under `{prefix}/sign/{mac}/`):

| Topic | Payload | Effect |
|-------|---------|--------|
| `reboot` | any | MCU reset |
| `display/set` | `ON` / `OFF` | Blank or show the matrix |
| `time/set` | ISO 8601 UTC, epoch, or `{"epoch": …}` | Set the device RTC |
| `data/publish` | any | Publish the full Data store to `data/state` |

Home Assistant autodiscovery is built in when MQTT is configured. See
`give_me_a_sign/home_assistant.py` for entity definitions.

## Displaying Images

Store the image as in indexed BMP format. Follow the code in nyan.py to display it. Can also load some GIFs and PNGs.

```
magick original.bmp -colors power-of-two output.bmp
```

Adafruit has [a good discussion of how to deal with indexed BMPs](https://learn.adafruit.com/creating-your-first-tilemap-game-with-circuitpython/indexed-bmp-graphics).

## Working with fonts

adafruit_bitmap_font.py

https://github.com/adafruit/Adafruit_CircuitPython_Bitmap_Font

## Weather Icons

## Home Assistant

Configure MQTT in `settings.toml` and set `SIGN_NAME` if you want a friendly
device name in Home Assistant. The sign publishes MQTT autodiscovery configs
for text entities, a display switch, a device-time datetime, reboot and
publish-data buttons, and diagnostic sensors.

Example — publish a message via MQTT (mosquitto_pub):

```
mosquitto_pub -h broker -t 'givemeasign/all/module/message' \
  -m '{"text": "Hello!", "color": 16711680}'
```

Set the clock (ISO 8601 UTC, as Home Assistant's datetime entity sends):

```
mosquitto_pub -h broker -t 'givemeasign/sign/aa_bb_cc_dd_ee_ff/time/set' \
  -m '2026-07-10T12:00:00+00:00'
```

Dump the in-memory Data store (also available as the **Publish Data Store**
button in Home Assistant):

```
mosquitto_pub -h broker -t 'givemeasign/sign/aa_bb_cc_dd_ee_ff/data/publish' \
  -m publish
# then: mosquitto_sub -h broker -t 'givemeasign/sign/aa_bb_cc_dd_ee_ff/data/state' -C 1
```

## Timezones
