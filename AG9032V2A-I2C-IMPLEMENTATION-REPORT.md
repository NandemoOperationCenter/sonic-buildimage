# AG9032V2A I2C/EEPROM Implementation Report

## Result

**PASS**

The installed build-6 image contains the bounded EEPROM-readiness fix and
passed cold-boot and controlled-reload acceptance on the AG9032V2A chassis.

```text
Image: SONiC-OS-fix_ag9032v2a-i2c-readiness.6-e9d61d0e6
Build commit: e9d61d0e6
Kernel: 6.12.41+deb13-sonic-amd64
Platform: x86_64-delta_ag9032v2a-r0
HwSKU: Delta-ag9032v2a
ASIC: broadcom
```

Final installed-image evidence:

```text
platform-modules-ag9032v2a.service: active (exited), status=0/SUCCESS
i2c_smbus.disable_spd: Y
buses 1--3: 3/3
buses 10--17: 8/8
buses 20--52: 33/33
transceiver clients: 33/33
readable transceiver EEPROMs: 33/33
board-ID client 1-0053: present and root-readable
root SPD clients 0-0050 through 0-0057: none
pmon, syncd, swss: active
xcvrd: RUNNING
CONFIG_DB front-panel ports: 33
STATE_DB front-panel ports: 33
Linux front-panel Ethernet interfaces: 33
Ethernet20: present with populated TRANSCEIVER_INFO and readable EEPROM
```

No current-boot occurrence was found for the EEPROM `-EBUSY` collision,
`get_transceiver_change_event` failure, `vendor_rev` failure, xcvrd fatal
processing, or the bounded-wait timeout.

## Problem and causal chain

The original Stage 2 image created all 33 Linux front-panel interfaces but did
not reliably provide the complete transceiver I2C topology.

The investigation established this causal chain:

1. DMI-based DDR4 SPD auto-instantiation could claim root SMBus EEPROM
   addresses such as `0x50`.
2. Linux mux address validation then rejected child front-panel clients at the
   same address with `-EBUSY`.
3. Suppressing automatic SPD registration before `i2c-i801` initialization
   removed the collision and allowed all 33 clients to register.
4. The legacy V2A plugin required the current
   `get_transceiver_change_event(timeout=0)` contract and a `hardware_rev` to
   `vendor_rev` compatibility alias for the installed xcvrd/base-library
   combination.
5. After those fixes, two cold boots showed a final service-status race:
   `modprobe delta_ag9032v2a_platform` returned before asynchronous EEPROM
   client registration had completed. The immediate 33-path test could fail
   even though the topology became healthy moments later.

The final fix replaces only that immediate test with a bounded readiness wait.

## Source and Git state

```text
Successful prior I2C merge on master:
  140194d91 merge AG9032V2A I2C topology fix

Readiness branch:
  fix/ag9032v2a-i2c-readiness

Readiness source commit:
  e9d61d0e65a2c52c249f1a728e9566d44c3abb75
  wait for ag9032v2a EEPROM topology readiness

Readiness merged commit:
  none; build 6 was produced directly from the focused branch commit
```

The readiness commit changes only:

```text
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/scripts/ag9032v2a_platform_init.sh
```

Commit summary:

```text
1 file changed, 27 insertions(+), 3 deletions(-)
```

It adds `wait_for_eeproms`, with:

- expected buses `20--52`;
- a 30-second overall timeout using Bash `SECONDS`;
- a 0.2-second sleep between polls;
- a freshly rebuilt missing-bus list on every poll;
- success only when all 33 EEPROM paths are readable;
- one final timeout error containing all missing bus numbers;
- non-zero timeout return to the existing `set -eu` caller.

The helper remains after the platform-module load and after the existing SWPLD
readiness checks. The SPD suppression and safe module reload logic are
unchanged.

No V2 file, kernel C module, package manifest, module parameter file, common
Delta script, Stage 2 BCM setting, premium Cancun selection, SAI profile,
`port_config.ini`, pmon, xcvrd, syncd, or swss source changed in this commit.

## Static verification

The committed source passed:

- `bash -n` on the modified init script;
- `git diff --check`;
- IDE diagnostics with no reported errors;
- branch-scope verification showing only the V2A init script;
- protected Stage 2 file checks;
- verification that no generated or sensitive file was staged.

An isolated temporary-directory harness exercised:

- all 33 paths immediately readable: PASS;
- paths becoming readable after a short delay: PASS;
- two permanently missing buses: non-zero timeout with both bus numbers;
- all 33 buses missing: non-zero timeout with all bus numbers.

The harness did not alter real `/sys`. Its temporary files were removed
automatically. The report was rewritten without the previous contradictory
`git diff --check` statement or trailing whitespace.

No C code changed, so no memory or string operation was added. No credential,
private key, token, certificate, log, package, image, core, or proprietary
binary was added to source control.

## Package and image build

The user rebuilt:

```text
platform-modules-ag9032v2a_1.1_amd64.deb
SONiC-OS-fix_ag9032v2a-i2c-readiness.6-e9d61d0e6
```

The first package-build attempt stopped while `sonic-build-hooks` tried to
resolve `packages.microsoft.com`. After the builder DNS configuration was
corrected, the package and image builds completed successfully. No source or
signature-verification bypass was used.

The extracted platform deb passed `bash -n` and contained:

```text
EEPROM_READY_TIMEOUT_SECONDS=30
EEPROM_READY_POLL_SECONDS=0.2
wait_for_eeproms
timed out waiting for V2A EEPROM buses
```

Installed package provenance:

```text
dpkg owner:
  platform-modules-ag9032v2a:
  /usr/local/bin/ag9032v2a_platform_init.sh

dpkg --verify platform-modules-ag9032v2a:
  no output

installed script:
  -rwxr-xr-x root:root
  size 1863 bytes
```

This proves the installed script is package-owned and has no detected local
modification. `sonic-device-data` did not require rebuilding for this isolated
readiness change.

## Cold-boot installed-image acceptance

The rebuilt image was installed and booted as the current and next image:

```text
Current: SONiC-OS-fix_ag9032v2a-i2c-readiness.6-e9d61d0e6
Next:    SONiC-OS-fix_ag9032v2a-i2c-readiness.6-e9d61d0e6
Prior:   SONiC-OS-master.5-140194d91
```

At evidence collection time, uptime was approximately seven minutes.

The cold-boot platform service reported:

```text
Result=success
ExecMainStatus=0
ActiveState=active
SubState=exited
```

Its measured `ExecMain` elapsed time was 450,852 microseconds, approximately
0.451 seconds. The service journal contained no timeout message. Because the
helper intentionally logs only final failure, its internal successful wait
cannot be separated from the complete service duration; the short total
duration is consistent with readiness on the initial poll or after at most a
short settle interval.

Cold-boot topology:

```text
buses 1--3: 3/3, none missing
buses 10--17: 8/8, none missing
buses 20--52: 33/33, none missing
transceiver clients: 33/33
readable EEPROMs: 33/33
root SPD clients 0-0050 through 0-0057: none
board-ID 1-0053: present and root-readable
```

Cold-boot service and interface state:

```text
pmon: active
syncd: active
swss: active
xcvrd: RUNNING
CONFIG_DB PORT records: 33
STATE_DB PORT_TABLE records: 33
Linux Ethernet interfaces: 33
```

Ethernet20 was present. The user read its installed-image EEPROM successfully,
and xcvrd populated `TRANSCEIVER_INFO|Ethernet20`. This is installed-image
evidence, not an earlier runtime hot update.

## Controlled installed-image reload cycles

The user explicitly approved exactly two reload cycles. The original state was
recorded as:

```text
pmon: active
xcvrd: RUNNING
```

For each cycle, pmon was stopped before the platform service. After each
platform-service stop:

```text
V2A platform nodes: 0
buses 1--3: 0
buses 10--17: 0
buses 20--52: 0
transceiver clients: 0
PCA9548 client 2-0071: absent
```

Cycle 1 platform start:

```text
Result: success
ExecMainStatus: 0
service duration: 114,354 microseconds
V2A platform nodes: 40
buses 1--3: 3/3
buses 10--17: 8/8
buses 20--52: 33/33
transceiver clients/readable EEPROMs: 33/33
PCA9548 client 2-0071: present
board-ID 1-0053: present and root-readable
xcvrd after pmon restore: RUNNING
Result: PASS
```

Cycle 2 platform start:

```text
Result: success
ExecMainStatus: 0
service duration: 114,428 microseconds
V2A platform nodes: 40
buses 1--3: 3/3
buses 10--17: 8/8
buses 20--52: 33/33
transceiver clients/readable EEPROMs: 33/33
PCA9548 client 2-0071: present
board-ID 1-0053: present and root-readable
xcvrd after pmon restore: RUNNING
Result: PASS
```

No stale node, bus collision, EEPROM timeout, or platform-service failure
occurred. Final post-cycle state:

```text
platform service, pmon, syncd, swss: active
xcvrd: RUNNING
platform Result: success
CONFIG_DB ports: 33
STATE_DB ports: 33
Linux Ethernet interfaces: 33
bounded-wait timeout occurrences: 0
target current-boot error occurrences: 0
```

## Earlier hot-test evidence

Before build 6, controlled runtime hot tests had proved the SPD suppression,
topology reconstruction, plugin compatibility, and optic visibility. Those
tests were useful implementation evidence but were not treated as final
acceptance.

The PASS result in this report is based on the package-owned script from the
installed build-6 image, its cold boot, and the two installed-image reload
cycles above.

## Residual risks

- This final phase verified an inserted optic and xcvrd data population but did
  not physically remove and reinsert the module to exercise a new hot-plug
  transition.
- Bash `SECONDS` has integer-second resolution. The 30-second bound can vary by
  less than one second at a boundary, while remaining finite and close to the
  configured timeout.
- The platform continues to use the established legacy plugin path rather than
  a platform-specific `sonic_platform` package. This did not prevent xcvrd or
  EEPROM acceptance.

## Rollback

Revert only the readiness commit:

```bash
git revert e9d61d0e65a2c52c249f1a728e9566d44c3abb75
```

If the readiness image regresses platform initialization, boot the prior image:

```text
SONiC-OS-master.5-140194d91
```

Do not revert the SPD suppression, V2A plugin compatibility, Stage 2 BCM
memory settings, common configuration inheritance, premium Cancun selection,
SAI profile, or EEPROM sysfs fixes.
