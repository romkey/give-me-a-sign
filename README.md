<!--
SPDX-FileCopyrightText: 2023 John Romkey

SPDX-License-Identifier: MIT
-->

# Give Me A Sign!

Give Me A Sign! is an info sign designed for hacker and makerspaces, although you could use it in your home or office as well.

The sign will mostly look like a clock, while sometimes displaying other useful information like messages, weather, air quality information or whatever you push to it.

The sign is intended to be deployed and left aone. It doesn't pull data (other than syncing its clock via NTP), data gets pushed to it. The project includes examples of how to set up Home Assistant to push data to the sign.

## Hardware

This code is designed to run on an [Adafruit MatrixPortal M4](https://www.adafruit.com/product/4745) board connected to a 64x32 LED matrix. It should work with other Adafruit Matrix products but it hasn't been tested with them and might need adapting.

## Update ESP32

https://learn.adafruit.com/upgrading-esp32-firmware/upgrade-all-in-one-esp32-airlift-firmware

Mine came with 1.2.2, current version is 1.7.4

## Update CircuitPython

https://circuitpython.org/board/matrixportal_m4/

## Update UF2 Bootloader

https://circuitpython.org/board/matrixportal_m4/

## Mounting

\#4-40 3/8" screws


## Installation

1. Follow the instructions

## API


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

```
service: rest_command.sign_tones
data:
  target: 10.0.1.123
  tones: '{ "frequency": 425, "duration": 0.5, "volume": 100 }, { "frequency": 100, "duration": 0.5, "volume": 100}'
```

## Timezones
