#!/bin/bash
set -eu

readonly PLATFORM_MODULE="delta_ag9032v2a_platform"
readonly SWPLD_PATH="/sys/devices/platform/delta-ag9032v2a-swpld1.0"
readonly EEPROM_READY_TIMEOUT_SECONDS=30
readonly EEPROM_READY_POLL_SECONDS=0.2
readonly REQUIRED_MODULES=(
    i2c-isch
    i2c-ismt
    i2c-dev
    i2c-mux
    i2c-mux-gpio
)

wait_for_eeproms()
{
    local deadline=$((SECONDS + EEPROM_READY_TIMEOUT_SECONDS))
    local bus
    local -a missing_buses=()

    while true; do
        missing_buses=()
        for bus in {20..52}; do
            [[ -r "/sys/bus/i2c/devices/${bus}-0050/eeprom" ]] ||
                missing_buses+=("$bus")
        done

        ((${#missing_buses[@]} == 0)) && return 0

        if ((SECONDS >= deadline)); then
            echo "timed out waiting for V2A EEPROM buses: ${missing_buses[*]}" >&2
            return 1
        fi

        sleep "$EEPROM_READY_POLL_SECONDS"
    done
}

case "${1:-start}" in
start)
    # The root SMBus and the front-panel mux branches share EEPROM addresses.
    # Suppress DMI-based SPD clients before i2c-i801 registers its adapter.
    if [[ -r /sys/module/i2c_smbus/parameters/disable_spd ]] &&
       [[ "$(< /sys/module/i2c_smbus/parameters/disable_spd)" != "Y" ]]; then
        if [[ -d /sys/module/i2c_i801 ]]; then
            modprobe -r i2c-i801
        fi
        if [[ -d /sys/module/i2c_smbus ]]; then
            modprobe -r i2c-smbus
        fi
    fi
    modprobe i2c-smbus disable_spd=1
    modprobe i2c-i801

    for module in "${REQUIRED_MODULES[@]}"; do
        modprobe "$module"
    done
    modprobe "$PLATFORM_MODULE"
    test -r "${SWPLD_PATH}/sfp_is_present"
    test -r "${SWPLD_PATH}/qsfp_lpmode"
    test -r "${SWPLD_PATH}/qsfp_reset"
    wait_for_eeproms
    ;;
stop)
    modprobe -r "$PLATFORM_MODULE"
    ;;
*)
    echo "usage: $0 {start|stop}" >&2
    exit 64
    ;;
esac

