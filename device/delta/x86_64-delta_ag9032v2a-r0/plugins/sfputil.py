# sfputil.py
#
# Platform-specific SFP transceiver interface for SONiC
#

try:
    import time
    from sonic_sfp.sfputilbase import SfpUtilBase
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))


class SfpUtil(SfpUtilBase):
    """Platform-specific SfpUtil class"""

    PORT_START = 0
    PORT_END = 32
    PORTS_IN_BLOCK = 33

    EEPROM_OFFSET = 20
    PRESENCE_PATH = "/sys/devices/platform/delta-ag9032v2a-swpld1.0/sfp_is_present"
    PRESENCE_POLL_INTERVAL = 1.0

    _port_to_eeprom_mapping = {}

    @property
    def port_start(self):
        return self.PORT_START

    @property
    def port_end(self):
        return self.PORT_END

    @property
    def qsfp_ports(self):
        return list(range(0, self.PORT_END - self.PORT_START + 1))

    @property
    def port_to_eeprom_mapping(self):
        return self._port_to_eeprom_mapping

    def __init__(self):
        eeprom_path = "/sys/bus/i2c/devices/{0}-0050/eeprom"

        for x in range(0, self.port_end + 1):
            self._port_to_eeprom_mapping[x] = eeprom_path.format(x + self.EEPROM_OFFSET)

        self.modprs_register = self._read_presence_register()
        SfpUtilBase.__init__(self)

    def _read_presence_register(self):
        try:
            with open(self.PRESENCE_PATH) as reg_file:
                return int(reg_file.readline().rstrip(), 16)
        except (IOError, ValueError) as e:
            print("Error: unable to read file: %s" % str(e))
            return None

    def get_presence(self, port_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            return False

        reg_value = self._read_presence_register()
        if reg_value is None:
            return False

        # Mask off the bit corresponding to our port
        mask = (1 << (self.port_end - port_num + 7))

        # ModPrsL is active low
        if reg_value & mask == 0:
            return True

        return False

    def get_low_power_mode(self, port_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end - 1:
            return False

        try:
            reg_file = open("/sys/devices/platform/delta-ag9032v2a-swpld1.0/qsfp_lpmode")
        except IOError as e:
            print("Error: unable to open file: %s" % str(e))

        content = reg_file.readline().rstrip()

        # content is a string containing the hex representation of the register
        reg_value = int(content, 16)

        # Mask off the bit corresponding to our port
        mask = (1 << (self.port_end - port_num) - 1)

        # LPMode is active high
        if reg_value & mask == 0:
            return False

        return True

    def set_low_power_mode(self, port_num, lpmode):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end - 1:
            return False

        try:
            reg_file = open("/sys/devices/platform/delta-ag9032v2a-swpld1.0/qsfp_lpmode", "r+")
        except IOError as e:
            print("Error: unable to open file: %s" % str(e))
            return False

        content = reg_file.readline().rstrip()

        # content is a string containing the hex representation of the register
        reg_value = int(content, 16)

        # Mask off the bit corresponding to our port
        mask = (1 << (self.port_end - port_num) - 1)

        # LPMode is active high; set or clear the bit accordingly
        if lpmode is True:
            reg_value = reg_value | mask
        else:
            reg_value = reg_value & ~mask

        # Convert our register value back to a hex string and write back
        content = hex(reg_value)

        reg_file.seek(0)
        reg_file.write(content)
        reg_file.close()

        return True

    def reset(self, port_num):
        QSFP_RESET_REGISTER_DEVICE_FILE = "/sys/devices/platform/delta-ag9032v2a-swpld1.0/qsfp_reset"

        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end - 1:
            return False

        try:
            reg_file = open(QSFP_RESET_REGISTER_DEVICE_FILE, "r+")
        except IOError as e:
            print("Error: unable to open file: %s" % str(e))
            return False

        content = reg_file.readline().rstrip()

        # File content is a string containing the hex representation of the register
        reg_value = int(content, 16)

        # Mask off the bit corresponding to our port
        mask = (1 << (self.port_end - port_num) - 1)

        # ResetL is active low
        reg_value = reg_value & ~mask

        # Convert our register value back to a hex string and write back
        reg_file.seek(0)
        reg_file.write(hex(reg_value))
        reg_file.close()

        # Sleep 1 second to allow it to settle
        time.sleep(1)

        # Flip the bit back high and write back to the register to take port out of reset
        try:
            reg_file = open(QSFP_RESET_REGISTER_DEVICE_FILE, "w")
        except IOError as e:
            print("Error: unable to open file: %s" % str(e))
            return False

        reg_value = reg_value | mask
        reg_file.seek(0)
        reg_file.write(hex(reg_value))
        reg_file.close()

        return True

    def get_transceiver_change_event(self, timeout=0):
        if timeout < 0:
            print("get_transceiver_change_event: Invalid timeout value", timeout)
            return False, {}

        deadline = None
        if timeout:
            deadline = time.monotonic() + timeout / 1000.0

        while True:
            reg_value = self._read_presence_register()
            if reg_value is None:
                return False, {'-1': 'system_not_ready'}

            if self.modprs_register is None:
                self.modprs_register = reg_value
            elif reg_value != self.modprs_register:
                changed_ports = self.modprs_register ^ reg_value
                port_dict = {}

                for port in range(self.port_start, self.port_end + 1):
                    mask = (1 << (self.port_end - port + 7))
                    if changed_ports & mask:
                        port_dict[port] = '0' if reg_value & mask else '1'

                self.modprs_register = reg_value
                return True, port_dict

            if deadline is None:
                time.sleep(self.PRESENCE_POLL_INTERVAL)
                continue

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True, {}

            time.sleep(min(self.PRESENCE_POLL_INTERVAL, remaining))
