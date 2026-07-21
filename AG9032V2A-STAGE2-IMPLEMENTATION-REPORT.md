# AG9032V2A Stage 2 Implementation Report

## Result

**PASS**

The controlled Stage 2 memory-profile change allowed Broadcom SAI 15.2 to
create the switch. All 33 expected front-panel Linux Ethernet interfaces are
present. The remaining transceiver-detection symptom is an independent
platform/I2C issue.

## Objective and scope

This test determined whether the following V2A-only BCM memory-profile changes
were sufficient to unblock SAI switch creation after common TD3 configuration
inheritance was enabled:

- remove `parity_enable=0`;
- change `mem_cache_enable=0` to `mem_cache_enable=1`;
- change `fpem_mem_entries=131072` to `fpem_mem_entries=0`.

No V2 files, common BCM files, port maps, lane maps, polarity values, bitmaps,
SAI/SDK packages, platform modules, services, or transceiver plugins were
changed.

## Branch and commits

- Branch: `test/ag9032v2a-stage2-memory-profile`
- Stage 1 base: `bf8a7dfaf2faa38913ec169edecdc75efc3215ae`
- Stage 2 commit: `01878761fc3371b28423f1d2dff0208ba464eb95`

## Exact source diff

```diff
diff --git a/device/delta/x86_64-delta_ag9032v2a-r0/Delta-ag9032v2a/td3-ag9032v2a-32x100G+1x10G.config.bcm b/device/delta/x86_64-delta_ag9032v2a-r0/Delta-ag9032v2a/td3-ag9032v2a-32x100G+1x10G.config.bcm
@@ -4,11 +4,10 @@
 core_clock_frequency=1525
 dpp_clock_ratio=2:3
 oversubscribe_mode=1
-parity_enable=0
-mem_cache_enable=0
+mem_cache_enable=1
 l2_mem_entries=32768
 l3_mem_entries=16384
-fpem_mem_entries=131072
+fpem_mem_entries=0
 l2xmsg_mode=1
 bcm_num_cos=10
 bcm_stat_interval=2000000
```

## Static verification

- The committed Stage 2 diff changes only the specified V2A BCM file.
- `git diff --check bf8a7dfaf..HEAD` passed.
- The committed diff is 2 insertions and 3 deletions.
- `common_config_support` remains an empty tracked file.
- The premium Cancun path remains
  `/etc/bcm/flex/bcm56870_a0_premium_issu/b870.6.15.0/`.
- No port map, lane map, polarity, bitmap, speed, alias, or index changed.
- No applicable standalone BCM syntax checker was identified.
- IDE lint reported no errors for the changed file.
- No credentials, keys, certificates, logs, cores, images, packages, or
  generated artifacts were staged or committed.

## User-performed package and image build

The user rebuilt the device-data package with:

```bash
rm -f target/debs/trixie/sonic-device-data_1.0-1_all.deb

make target/debs/trixie/sonic-device-data_1.0-1_all.deb
```

The extracted package passed these checks:

```text
parity_enable: absent
mem_cache_enable=1
fpem_mem_entries=0
sai_load_hw_config=/etc/bcm/flex/bcm56870_a0_premium_issu/b870.6.15.0/
```

The requested image build command was:

```bash
rm -f target/sonic-broadcom.bin

BUILD_NUMBER=3 \
SONIC_CONFIG_MAKE_JOBS=104 \
SONIC_BUILD_JOBS=32 \
NOBOOKWORM=1 \
make target/sonic-broadcom.bin
```

The user installed the resulting image and rebooted the chassis.

## Installed image and platform

Hardware evidence was collected from the current boot on
`10.254.0.190` on 2026-07-21.

```text
Image: SONiC-OS-test_ag9032v2a-stage2-memory-profile.3-01878761f
Build commit: 01878761f
Kernel: 6.12.41+deb13-sonic-amd64
Platform: x86_64-delta_ag9032v2a-r0
HwSKU: Delta-ag9032v2a
ASIC: broadcom
libsaibcm: 15.2.0.0.0.0.3.1
OCP SAI: 1.18.1
SDK: sdk-6.5.35-SP1
```

## Effective merged BCM configuration

The runtime marker exists and is empty at:

```text
/usr/share/sonic/device/x86_64-delta_ag9032v2a-r0/common_config_support
```

The syncd log explicitly recorded the merge of:

```text
/usr/share/sonic/device/x86_64-broadcom_common/x86_64-broadcom_b87/broadcom-sonic-td3.config.bcm
```

into the V2A temporary BCM configuration. Relevant effective values were:

```text
parity_enable: absent
mem_cache_enable=1
fpem_mem_entries=0
sai_load_hw_config=/etc/bcm/flex/bcm56870_a0_premium_issu/b870.6.15.0/
sai_optimized_mmu=1
sai_mmu_tc_to_pg_config=1
```

This confirms both V2A board-value precedence and common TD3 inheritance.

## Port pipeline evidence

```text
CONFIG_DB PORT records:       33
APPL_DB PORT_TABLE keys:      35
  Front-panel port records:   33
  Completion markers:          2 (PortConfigDone, PortInitDone)
STATE_DB PORT_TABLE records:  33
ASIC_DB switch objects:        1
ASIC_DB port objects:         34
Linux front-panel Ethernet:   33
```

`show interface status` listed all expected interfaces from `Ethernet0`
through `Ethernet128`. `Ethernet20` was operationally up during collection;
other disconnected ports were down, which is acceptable for this test.

The 34 ASIC port objects account for the 33 front-panel ports plus the CPU
port. This differs from the Enterprise baseline count of 37 but does not leave
any expected front-panel interface missing.

## Successful SAI initialization sequence

Minimal current-boot evidence:

```text
05:28:11 common b87 TD3 BCM configuration merged into the V2A temporary file
05:28:12 request switch create with context 0
05:28:12 creating switch number 1
05:28:12 Initializing Broadcom SAI driver
05:28:14 SDK init completed in 1.852503 seconds
05:28:15 Total switch-create time 2.372198 seconds
05:28:15 Switch: created switch with hwinfo = ''
```

No `SAI_STATUS_FAILURE` occurred during switch creation. Later unsupported
attribute/API notices did not abort initialization, and both `syncd` and
`swss` remained active.

## Acceptance assessment

- syncd remains running: PASS
- swss remains running: PASS
- SAI switch creation succeeds: PASS
- exactly one ASIC switch exists: PASS
- expected front-panel ASIC/Linux ports exist: PASS
- all 33 front-panel Ethernet interfaces exist: PASS
- CONFIG_DB/APPL_DB/STATE_DB contain expected records: PASS
- V2A premium profile remains selected: PASS
- common TD3 merge occurs: PASS

Overall Stage 2 result: **PASS**.

The original Stage 1 failure mode—33 CONFIG_DB ports but zero Linux Ethernet
interfaces—is no longer present.

## Independent I2C/transceiver issue

The separate I2C defect remains unresolved:

- expected I2C adapter buses 10--17 are absent;
- expected transceiver buses 20--52 are absent;
- all expected EEPROM paths on buses 20--52 are absent;
- `platform-modules-ag9032v2a.service` reports active/exited successfully;
- `pmon.service` is running;
- `i2cdetect` is not installed on the chassis.

Consequently, a command concerned with transceiver/EEPROM visibility may still
report that ports or modules are not recognized even though all 33 network
interfaces now exist. No I2C, platform-module, service, or `sfputil.py` change
was made in Stage 2.

## Risks and unresolved questions

- The cause of the missing I2C topology remains unknown and requires a separate
  approved investigation.
- `/usr/share/sonic/platform/common_config_support` is absent because the
  runtime platform path is not linked to the device directory on this image.
  The marker is present in the device platform directory, and the syncd log
  proves that the common merge ran successfully.
- The OCP image creates 34 ASIC port objects versus 37 in the Enterprise
  baseline. All 33 expected front-panel ports and one CPU port are present, but
  the three-object difference should be documented if exact cross-version ASIC
  object parity becomes a requirement.
- Startup emitted transient `linux-bcm-knet` messages stating that Ethernet
  devices could not yet be found. Subsequent database and Linux state confirms
  successful creation of all interfaces.

## Rollback

From the Stage 2 branch, create a focused revert with:

```bash
git revert 01878761fc3371b28423f1d2dff0208ba464eb95
```

Do not revert the Stage 1 common-config marker, premium Cancun selection, or
EEPROM sysfs commits.
