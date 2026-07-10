#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

# Shared helpers for MQTT integration tests against a live sign.
#
# Required:
#   BROKER   - MQTT broker hostname or IP
#
# Optional:
#   PREFIX   - topic prefix (default: givemeasign)
#   SIGN     - per-device topic base, e.g. givemeasign/sign/aa_bb_cc_dd_ee_ff
#   MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

: "${BROKER:?Set BROKER to your MQTT broker hostname or IP}"
: "${PREFIX:=givemeasign}"

MOSQUITTO_PUB="mosquitto_pub -h ${BROKER}"
MOSQUITTO_SUB="mosquitto_sub -h ${BROKER}"

if [ -n "${MQTT_PORT}" ]; then
    MOSQUITTO_PUB="${MOSQUITTO_PUB} -p ${MQTT_PORT}"
    MOSQUITTO_SUB="${MOSQUITTO_SUB} -p ${MQTT_PORT}"
fi

if [ -n "${MQTT_USERNAME}" ]; then
    MOSQUITTO_PUB="${MOSQUITTO_PUB} -u ${MQTT_USERNAME} -P ${MQTT_PASSWORD}"
    MOSQUITTO_SUB="${MOSQUITTO_SUB} -u ${MQTT_USERNAME} -P ${MQTT_PASSWORD}"
fi

publish_all() {
    endpoint="$1"
    payload="$2"
    echo "PUBLISH ${PREFIX}/all/module/${endpoint} ${payload}"
    ${MOSQUITTO_PUB} -t "${PREFIX}/all/module/${endpoint}" -m "${payload}"
}

publish_sign_module() {
    endpoint="$1"
    payload="$2"
    : "${SIGN:?Set SIGN to the sign topic base (givemeasign/sign/MAC_with_underscores)}"
    echo "PUBLISH ${SIGN}/module/${endpoint} ${payload}"
    ${MOSQUITTO_PUB} -t "${SIGN}/module/${endpoint}" -m "${payload}"
}

publish_sign() {
    topic="$1"
    payload="$2"
    : "${SIGN:?Set SIGN to the sign topic base (givemeasign/sign/MAC_with_underscores)}"
    echo "PUBLISH ${SIGN}/${topic} ${payload}"
    ${MOSQUITTO_PUB} -t "${SIGN}/${topic}" -m "${payload}"
}

now_epoch() {
    date +%s
}
