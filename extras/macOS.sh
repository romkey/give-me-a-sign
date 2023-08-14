# https://learn.adafruit.com/welcome-to-circuitpython/troubleshooting

mdutil -i off /Volumes/CIRCUITPY
cd /Volumes/CIRCUITPY
rm -rf {.fseventsd,.Spotlight-V*}
rm ._*
cd lib
rm ._*
cd ../assets
rm ._*
cd fonts
rm ._*

mkdir .fseventsd
touch .fseventsd/no_log .metadata_never_index .Trashes
