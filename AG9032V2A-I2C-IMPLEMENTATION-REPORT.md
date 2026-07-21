# AG9032V2A I2C/EEPROM Implementation Report

## Result

**SOURCE FIX IMPLEMENTED AND PROVEN BY CONTROLLED RUNTIME TEST**

The installed image `SONiC-OS-fix_ag9032v2a-i2c-topology.4-97034b770`
contains the first userspace fix, but a cold boot exposed two additional
failures:

- DMI-based DDR4 SPD auto-instantiation claimed root SMBus address `0x50`,
  causing all 33 front-panel `optoe` clients to fail with `-EBUSY`;
- after restoring the EEPROM clients, current `SfpUtilBase` returned
  `hardware_rev`, while the installed `xcvrd` required `vendor_rev` and exited
  with `KeyError`.

The V2A platform init now disables automatic SPD registration before loading
`i2c_i801`, reloads those modules if they were already loaded with the default,
and verifies all 33 EEPROM sysfs paths. The V2A plugin aliases `hardware_rev`
to `vendor_rev`. A controlled runtime test reproduced the cold-boot collision
and proved automatic recovery:

```text
Before fixed service start:
  i2c_smbus.disable_spd=N
  root DDR4 SPD 0-0050: present

After fixed service start:
  i2c_smbus.disable_spd=Y
  root DDR4 SPD 0-0050: absent
  front-panel clients: 33/33
  readable EEPROM paths: 33/33
  xcvrd: RUNNING
  Ethernet20 presence: Present
  Ethernet20 EEPROM: detected
```

The source still requires user-performed package and image builds. Runtime
files on the test chassis were hot-updated only to verify the implementation.

## Observed symptom and causal chain

On the installed image, buses 1--3, 10--17, and 20--52 existed, but all
front-panel clients were absent. The first kernel errors were:

```text
i2c i2c-20: Failed to register i2c client optoe1 at 0x50 (-16)
delta-ag9032v2a-i2c-device.1: Failed to create i2c client optoe1 at 20
```

The same `-EBUSY` failure repeated through bus 52. Runtime ownership proved:

```text
0-0050 name=ee1004
driver=/sys/bus/i2c/drivers/ee1004
```

Linux checks duplicate addresses across a mux parent/child tree. Therefore the
root `0-0050` client blocked every child `20-0050` through `52-0050`.

After setting `i2c_smbus.disable_spd=Y` and rebuilding the topology, all EEPROM
paths became readable and Ethernet20 returned identifier `0x11`. This exposed
the next userspace error:

```text
KeyError('vendor_rev')
```

`SfpUtilBase.get_transceiver_info_dict()` returned `hardware_rev`; the installed
`xcvrd` indexed `vendor_rev` unconditionally. Adding the compatibility alias
allowed `xcvrd` to populate `TRANSCEIVER_INFO|Ethernet20`.

## Baseline identity and service evidence

```text
Image: SONiC-OS-fix_ag9032v2a-i2c-topology.4-97034b770
Build commit: 97034b770
Kernel: 6.12.41+deb13-sonic-amd64
Platform: x86_64-delta_ag9032v2a-r0
HwSKU: Delta-ag9032v2a
ASIC: broadcom
Platform package: platform-modules-ag9032v2a 1.1
```

Final controlled-test service state:

```text
platform-modules-ag9032v2a.service: active
pmon.service: active
syncd.service: active
swss.service: active
pmon supervisor xcvrd process: RUNNING
CONFIG_DB front-panel PORT records: 33
STATE_DB PORT_TABLE records: 33
STATE_DB TRANSCEIVER_INFO|Ethernet20: populated
```

## Hypotheses

### Ruled out

- Wrong platform or HWSKU: runtime identity is exactly V2A.
- Missing or unloaded V2A module: the module is loaded.
- CPLD mux failure: buses 1--3 are present.
- PCA9548 client or fixed-bus failure: `2-0071` and buses 10--17 are present.
- SWPLD mux failure: buses 20--52 are present.
- Stale nodes or unload cleanup defect: neither controlled stop left V2A nodes.
- Stage 2 SAI regression: all 33 ports remain present and syncd/swss are active.

### Ruled in

- Automatic SPD registration is nondeterministic with respect to the populated
  DMI slot address. When it claims root `0x50`, all child front-panel `0x50`
  clients fail Linux mux address validation with `-EBUSY`.
- The kernel already carries the SONiC `i2c_smbus.disable_spd` parameter for
  this class of switch-platform collision; it was left at its default `N`.
- The V2A legacy plugin needed both the previously implemented
  `get_transceiver_change_event(timeout=0)` contract and a `vendor_rev`
  compatibility alias for the installed xcvrd/base-library combination.

## Branch and implementation state

```text
Branch: fix/ag9032v2a-i2c-topology
Base: c84f15c10
Initial plugin commit: 97034b770ccaf48b8a25a3f9481f4ab8d57828fb
SPD/vendor_rev follow-up: this report's focused follow-up commit
```

## Initial committed source diff

The initial commit changed only this V2A file:

```text
device/delta/x86_64-delta_ag9032v2a-r0/plugins/sfputil.py
```

```diff
@@
     EEPROM_OFFSET = 20
+    PRESENCE_PATH = "/sys/devices/platform/delta-ag9032v2a-swpld1.0/sfp_is_present"
+    PRESENCE_POLL_INTERVAL = 1.0
@@
+        self.modprs_register = self._read_presence_register()
         SfpUtilBase.__init__(self)
 
+    def _read_presence_register(self):
+        try:
+            with open(self.PRESENCE_PATH) as reg_file:
+                return int(reg_file.readline().rstrip(), 16)
+        except (IOError, ValueError) as e:
+            print("Error: unable to read file: %s" % str(e))
+            return None
+
     def get_presence(self, port_num):
@@
-        try:
-            reg_file = open("/sys/devices/platform/delta-ag9032v2a-swpld1.0/sfp_is_present")
-        except IOError as e:
-            print("Error: unable to open file: %s" % str(e))
+        reg_value = self._read_presence_register()
+        if reg_value is None:
             return False
-
-        content = reg_file.readline().rstrip()
-
-        # content is a string containing the hex representation of the register
-        reg_value = int(content, 16)
@@
-    def get_transceiver_change_event(self):
-        """
-        TODO: This function need to be implemented
-        when decide to support monitoring SFP(Xcvrd)
-        on this platform.
-        """
-        raise NotImplementedError
+    def get_transceiver_change_event(self, timeout=0):
+        if timeout < 0:
+            print("get_transceiver_change_event: Invalid timeout value", timeout)
+            return False, {}
+
+        deadline = None
+        if timeout:
+            deadline = time.monotonic() + timeout / 1000.0
+
+        while True:
+            reg_value = self._read_presence_register()
+            if reg_value is None:
+                return False, {'-1': 'system_not_ready'}
+
+            if self.modprs_register is None:
+                self.modprs_register = reg_value
+            elif reg_value != self.modprs_register:
+                changed_ports = self.modprs_register ^ reg_value
+                port_dict = {}
+
+                for port in range(self.port_start, self.port_end + 1):
+                    mask = (1 << (self.port_end - port + 7))
+                    if changed_ports & mask:
+                        port_dict[port] = '0' if reg_value & mask else '1'
+
+                self.modprs_register = reg_value
+                return True, port_dict
+
+            if deadline is None:
+                time.sleep(self.PRESENCE_POLL_INTERVAL)
+                continue
+
+            remaining = deadline - time.monotonic()
+            if remaining <= 0:
+                return True, {}
+
+            time.sleep(min(self.PRESENCE_POLL_INTERVAL, remaining))
```

The initial committed summary is 50 insertions and 16 deletions in one file.

## Current source delta

Four V2A-specific files have follow-up changes:

```text
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/scripts/ag9032v2a_platform_init.sh
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/cfg/ag9032v2a-params.conf
platform/broadcom/sonic-platform-modules-delta/debian/platform-modules-ag9032v2a.install
device/delta/x86_64-delta_ag9032v2a-r0/plugins/sfputil.py
```

The package installs `options i2c-smbus disable_spd=1` under
`/etc/modprobe.d`, ensuring that the earlier modules-load phase applies the
policy when `i2c-i801` first loads.

The init script:

- loads `i2c-smbus` with `disable_spd=1` before `i2c-i801`;
- if the modules were auto-loaded earlier with `disable_spd=N`, unloads and
  reloads them in the safe order;
- verifies all 33 `/sys/bus/i2c/devices/20-0050/eeprom` through
  `/sys/bus/i2c/devices/52-0050/eeprom` paths before service success.

The plugin adds:

```python
def get_transceiver_info_dict(self, port_num):
    info = SfpUtilBase.get_transceiver_info_dict(self, port_num)
    if info is not None and 'vendor_rev' not in info and 'hardware_rev' in info:
        info['vendor_rev'] = info['hardware_rev']
    return info
```

## Why the fix preserves V2A identity and topology

- The path retains the `delta-ag9032v2a-*` sysfs prefix.
- Physical ports remain 0--32.
- EEPROM buses remain 20--52.
- Existing active-low presence-bit mapping is reused.
- No V2 file, kernel C module, bus number, BCM setting, SAI profile,
  port configuration, or package integration file changed.
- The SPD policy is applied only by the V2A platform service and uses an
  existing kernel parameter already carried by this SONiC kernel.
- The method now implements the current base-class contract: timeout is in
  milliseconds, zero blocks until an event, timeout expiry returns a successful
  empty event, and sysfs unavailability returns `system_not_ready`.

## Static verification

- `python3 -m py_compile .../plugins/sfputil.py`: PASS.
- `bash -n .../scripts/ag9032v2a_platform_init.sh`: PASS.
- Direct contract checks for insertion, timeout, invalid timeout, and
  `system_not_ready`: PASS.
- Controlled `vendor_rev` compatibility test through xcvrd: PASS.
- Controlled init-script test from `disable_spd=N` and root `0-0050`: PASS.
- `git diff --check`: PASS.
- IDE lint diagnostics: no errors.
- Follow-up scope: exactly four V2A files plus this report.
- Protected Stage 2 BCM, common-config marker, SAI profile, and
  `port_config.ini`: unchanged.
- No C code changed; therefore no memory/string function was introduced.
- No credentials, keys, tokens, certificates, logs, images, packages, or
  generated artifacts were added.

## Controlled two-cycle reload result

The user approved two platform-service reload cycles. `pmon` was stopped
during the experiment and restored afterward.

For both cycles:

```text
After stop:
  V2A platform nodes: 0
  buses 1--3: absent
  buses 10--17: 0
  buses 20--52: 0
  transceiver clients/readable EEPROMs: 0/0
  2-0071: absent

After start:
  V2A platform nodes: 40
  buses 1--3: present
  buses 10--17: 8
  buses 20--52: 33
  transceiver clients/readable EEPROMs: 33/33
  2-0071: present
  board-ID client 1-0053: absent (-EBUSY)
```

No stale V2A node or fixed-bus collision occurred.

## Controlled cold-conflict reproduction and fixed-service result

The user approved a follow-up controlled test. The runtime was deliberately
returned to the failing cold-boot condition, then started using the modified
service script:

```text
Reproduced:
  i2c_smbus.disable_spd=N
  root SPD 0-0050: present

Fixed service result:
  i2c_smbus.disable_spd=Y
  root SPD 0-0050: absent
  front-panel clients/readable paths: 33/33
  Ethernet20 EEPROM identifier: 0x11
  xcvrd: RUNNING
  Ethernet20: Present
  TRANSCEIVER_INFO|Ethernet20: populated
  show interfaces transceiver eeprom Ethernet20: detected
```

The previously conflicting board-ID client `1-0053` is now instantiated
because no root SPD client reserves address `0x53`. Its driver-level EEPROM
readability remains a separate board-ID concern.

## User package and image build

Not yet performed. Rebuild both changed packages.

Platform package:

```bash
rm -f target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb

make PLATFORM=broadcom \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb
```

Device-data package containing the plugin:

```bash
rm -f target/debs/trixie/sonic-device-data_1.0-1_all.deb

make target/debs/trixie/sonic-device-data_1.0-1_all.deb
```

Inspect the package before the image build:

```bash
rm -rf /tmp/ag9032v2a-i2c-platform
dpkg-deb -x \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb \
  /tmp/ag9032v2a-i2c-platform

bash -n \
  /tmp/ag9032v2a-i2c-platform/usr/local/bin/ag9032v2a_platform_init.sh

rm -rf /tmp/ag9032v2a-i2c-device-data
dpkg-deb -x \
  target/debs/trixie/sonic-device-data_1.0-1_all.deb \
  /tmp/ag9032v2a-i2c-device-data

python3 -m py_compile \
  /tmp/ag9032v2a-i2c-device-data/usr/share/sonic/device/x86_64-delta_ag9032v2a-r0/plugins/sfputil.py
```

Then use a new image build number:

```bash
rm -f target/sonic-broadcom.bin

BUILD_NUMBER=5 \
SONIC_CONFIG_MAKE_JOBS=104 \
SONIC_BUILD_JOBS=32 \
NOBOOKWORM=1 \
make target/sonic-broadcom.bin
```

## Installed-image acceptance still required

After installation, verify:

- installed image and build commit;
- 33 CONFIG_DB and 33 STATE_DB front-panel ports;
- 33 Linux front-panel Ethernet interfaces;
- syncd and swss active;
- platform service active;
- `/sys/module/i2c_smbus/parameters/disable_spd` reports `Y`;
- no root `0-0050` or other DMI-created SPD client blocks mux addresses;
- buses 1--3, 10--17, and 20--52 present;
- all 33 front-panel EEPROM clients/files present and readable;
- `docker exec pmon supervisorctl status xcvrd` reports `RUNNING`;
- no `TypeError` from `get_transceiver_change_event`;
- no `KeyError('vendor_rev')`;
- Ethernet20 is present and its `TRANSCEIVER_INFO` record is populated;
- insertion/removal events are reflected by xcvrd;
- two reload cycles remain clean.

Current acceptance is **BLOCKED** because the new package/image has not been
built or installed. Runtime hot-testing passed but does not replace a cold boot
from the rebuilt image.

## Unresolved risks

- Board-ID client `1-0053` now instantiates, but its driver-level EEPROM
  readability has not been resolved.
- Hardware insertion/removal event behavior must be tested after installation.
- The current image lacks a platform-specific `sonic_platform` package. This is
  expected for this legacy-plugin platform, but it causes non-fatal chassis/SFP
  object warnings before xcvrd falls back to `sfputil`.

## Rollback

The initial plugin commit can be reverted with:

```bash
git revert 97034b770ccaf48b8a25a3f9481f4ab8d57828fb
```

Revert only the focused SPD/vendor_rev follow-up commits to remove the current
four-file source change.

Do not revert Stage 2 BCM/common-config, premium Cancun, or EEPROM sysfs
commits.
