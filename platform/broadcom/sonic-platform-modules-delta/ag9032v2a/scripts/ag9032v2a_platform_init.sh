#!/bin/bash
set -eu

readonly PLATFORM_MODULE="delta_ag9032v2a_platform"
readonly SWPLD_PATH="/sys/devices/platform/delta-ag9032v2a-swpld1.0"
readonly REQUIRED_MODULES=(
    i2c-i801
    i2c-isch
    i2c-ismt
    i2c-dev
    i2c-mux
    i2c-smbus
    i2c-mux-gpio
)

case "${1:-start}" in
start)
    for module in "${REQUIRED_MODULES[@]}"; do
        modprobe "$module"
    done
    modprobe "$PLATFORM_MODULE"
    test -r "${SWPLD_PATH}/sfp_is_present"
    test -r "${SWPLD_PATH}/qsfp_lpmode"
    test -r "${SWPLD_PATH}/qsfp_reset"
    ;;
stop)
    modprobe -r "$PLATFORM_MODULE"
    ;;
*)
    echo "usage: $0 {start|stop}" >&2
    exit 64
    ;;
esac

