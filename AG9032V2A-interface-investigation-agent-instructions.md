# Investigate AG9032V2A interfaces missing after successful image build

## Objective

Determine why a successfully built and installed Broadcom SONiC image does not
recognize the Delta AG9032V2A front-panel interfaces, then implement the
narrowest evidence-based fix.

Do not assume that this is a `port_config.ini` problem. First identify which
layer fails:

1. platform and HWSKU selection;
2. CONFIG_DB port generation;
3. Broadcom SAI/syncd initialization;
4. swss/orchagent interface creation;
5. platform kernel module and I2C topology;
6. xcvrd/SFP sysfs access.

The distinction matters: missing `Ethernet*` records is different from ports
existing but showing no link, no transceiver, or no EEPROM.

## Repository and target

- Repository: `/mnt/nvme1/sonic-buildimage`
- Platform: `x86_64-delta_ag9032v2a-r0`
- HWSKU: `Delta-ag9032v2a`
- ASIC: Broadcom Trident3 / BCM56870
- Target OS: Debian Trixie
- Target kernel: `6.12.41+deb13-sonic-amd64`
- Image target: `target/sonic-broadcom.bin`

V2A uses the premium BCM56870 ISSU profile. Do not substitute V2's non-premium
profile.

## Mandatory workflow

1. Review root `git status`, staged and unstaged diffs, recent commits, and
   relevant submodule status before editing anything.
2. Preserve every existing user change and generated artifact. Never reset,
   restore, clean, or overwrite unrelated work.
3. Create a new branch before implementation changes. If editing a nested Git
   repository, create and commit a focused branch there first, then commit the
   parent gitlink update separately.
4. Commit every implementation change with a focused message. Do not amend or
   push.
5. Do not edit `rules/config`.
6. Do not modify AG9032V2 files unless hardware evidence proves that a shared
   fix is required. Keep V2 and V2A identifiers, modules, sysfs names, and
   BCM/SAI profiles distinct.
7. Do not run image, package, Docker, or hardware builds. The user performs
   those manually. Provide exact commands and wait for results.
8. Do not commit logs, generated output, temporary build directories, image
   artifacts, credentials, keys, certificates, or tokens.
9. For C changes, do not introduce unbounded string/memory functions. Preserve
   explicit resource cleanup and error propagation.

## Known architecture

V2A uses legacy device plugins and `port_config.ini`; it does not have a
platform-specific `sonic_platform` Python package.

Expected runtime path:

```text
/host/machine.conf
  -> onie_platform=x86_64-delta_ag9032v2a-r0
  -> device/delta/x86_64-delta_ag9032v2a-r0/default_sku
  -> Delta-ag9032v2a
  -> port_config.ini populates CONFIG_DB PORT records
  -> sai.profile selects the V2A BCM config
  -> syncd initializes SAI
  -> swss/orchagent creates APPL_DB and Linux interfaces
```

The platform module separately creates the CPLD/I2C topology required by
xcvrd and the legacy `sfputil.py`:

- PCA9548 buses: 10--17
- transceiver EEPROM buses: 20--52
- 33 front-panel ports/EEPROMs
- V2A sysfs prefix: `delta-ag9032v2a-*`
- kernel module: `delta_ag9032v2a_platform.ko`

## Phase 1: collect hardware evidence before editing

Ask the user to run the following commands on the affected switch and return
the complete output. Do not propose a code change until the failing layer is
identified.

### A. Platform and HWSKU identity

```bash
cat /host/machine.conf
show platform summary
sonic-cfggen -H -v DEVICE_METADATA.localhost.platform
sonic-db-cli CONFIG_DB HGETALL 'DEVICE_METADATA|localhost'
```

Acceptance:

- platform is exactly `x86_64-delta_ag9032v2a-r0`;
- HWSKU is exactly `Delta-ag9032v2a`;
- ASIC type is Broadcom.

### B. Installed device data

```bash
PLATFORM=$(sonic-cfggen -H -v DEVICE_METADATA.localhost.platform)
ls -la "/usr/share/sonic/device/$PLATFORM"
cat "/usr/share/sonic/device/$PLATFORM/default_sku"
ls -la "/usr/share/sonic/device/$PLATFORM/Delta-ag9032v2a"
cat "/usr/share/sonic/device/$PLATFORM/Delta-ag9032v2a/sai.profile"
wc -l "/usr/share/sonic/device/$PLATFORM/Delta-ag9032v2a/port_config.ini"
```

Verify that `sai.profile` points to:

```text
td3-ag9032v2a-32x100G+1x10G.config.bcm
```

and that the BCM configuration uses the V2A premium path:

```text
bcm56870_a0_premium_issu
```

### C. Determine whether logical ports were generated

```bash
test -e /etc/sonic/pending_config_initialization && echo pending || echo initialized
sonic-db-cli CONFIG_DB GET CONFIG_DB_INITIALIZED
sonic-db-cli CONFIG_DB KEYS 'PORT|*' | sort
sonic-db-cli APPL_DB KEYS 'PORT_TABLE:*' | sort
sonic-db-cli STATE_DB KEYS 'PORT_TABLE|*' | sort
show interface status
ip -br link
```

Expected: 33 CONFIG_DB port records corresponding to 32 x 100G plus 1 x 10G.

Interpretation:

- no CONFIG_DB `PORT|*`: platform/HWSKU/config initialization defect;
- CONFIG_DB ports exist but APPL_DB ports do not: swss/orchagent or syncd
  initialization defect;
- APPL_DB ports exist but Linux interfaces do not: orchagent/syncd failure;
- interfaces exist but optics are absent: platform module/I2C/xcvrd defect.

### D. Platform package, service, and kernel module

```bash
dpkg -l | grep -E 'platform-modules-ag9032v2a|linux-image'
systemctl status platform-modules-ag9032v2a.service --no-pager
journalctl -u platform-modules-ag9032v2a.service -b --no-pager
lsmod | grep delta_ag9032
modinfo delta_ag9032v2a_platform
ls /sys/devices/platform | grep delta-ag9032v2a
```

Confirm module vermagic matches the running kernel:

```bash
uname -r
modinfo -F vermagic delta_ag9032v2a_platform
```

### E. Required I2C and SFP topology

```bash
i2cdetect -l
for bus in $(seq 10 17) $(seq 20 52); do
    test -d "/sys/class/i2c-adapter/i2c-$bus" || echo "missing i2c-$bus"
done
for bus in $(seq 20 52); do
    test -r "/sys/class/i2c-adapter/i2c-$bus/$bus-0050/eeprom" ||
        echo "missing EEPROM bus $bus"
done
ls -la /sys/devices/platform/delta-ag9032v2a-swpld1.0/
systemctl status pmon xcvrd --no-pager
journalctl -u pmon -u xcvrd -b --no-pager
```

### F. syncd, SAI, and swss

```bash
systemctl status syncd swss --no-pager
docker ps -a | grep -E 'syncd|swss'
docker exec syncd cat /usr/share/sonic/hwsku/sai.profile
docker exec syncd ls -la /usr/share/sonic/hwsku/
docker logs syncd 2>&1
docker logs swss 2>&1
journalctl -u syncd -u swss -b --no-pager
```

Find the first SAI/BCM/orchagent error rather than relying on later cascading
messages.

## Phase 2: source files to inspect

### Platform and HWSKU identity

```text
device/delta/x86_64-delta_ag9032v2a-r0/default_sku
device/delta/x86_64-delta_ag9032v2a-r0/platform_asic
device/delta/x86_64-delta_ag9032v2a-r0/installer.conf
installer/platforms/x86_64-delta_ag9032v2a-r0
```

Edit these only if the installed machine/HWSKU identity is demonstrably wrong.

### Logical port definitions

Primary file:

```text
device/delta/x86_64-delta_ag9032v2a-r0/Delta-ag9032v2a/port_config.ini
```

Validate all 33 entries:

- logical names `Ethernet0` through `Ethernet128`;
- aliases `hundredGigE1/1` through `hundredGigE1/32` and `tenGigE1/33`;
- lane values;
- indices 0--32;
- speeds 100000/10000.

Do not change lane or index mappings without board documentation or a known-good
V2A image/configuration as evidence.

### Broadcom SAI/BCM initialization

```text
device/delta/x86_64-delta_ag9032v2a-r0/Delta-ag9032v2a/sai.profile
device/delta/x86_64-delta_ag9032v2a-r0/Delta-ag9032v2a/td3-ag9032v2a-32x100G+1x10G.config.bcm
platform/broadcom/docker-syncd-brcm/start.sh
```

Inspect `portmap_*`, PHY lane maps, polarity settings, and
`sai_load_hw_config`. Never copy the V2 non-premium configuration over V2A.

### Platform kernel module and service

```text
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/modules/delta_ag9032v2a_platform.c
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/modules/Makefile
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/cfg/ag9032v2a-modules.conf
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/scripts/ag9032v2a_platform_init.sh
platform/broadcom/sonic-platform-modules-delta/systemd/platform-modules-ag9032v2a.service
platform/broadcom/sonic-platform-modules-delta/debian/platform-modules-ag9032v2a.install
platform/broadcom/sonic-platform-modules-delta/debian/control
platform/broadcom/sonic-platform-modules-delta/debian/rules
```

Check probe order, adapter numbering, cleanup/error paths, module loading,
service ordering, and readiness checks. The service must fail visibly if the
required module or sysfs nodes are absent.

### Image integration

```text
platform/broadcom/platform-modules-delta-v2a.mk
platform/broadcom/platform-modules-delta-v2a.dep
platform/broadcom/rules.mk
platform/broadcom/rules.dep
platform/broadcom/one-image.mk
files/image_config/platform/rc.local
files/build_templates/sonic_debian_extension.j2
src/sonic-device-data/Makefile
```

Confirm the V2A platform deb is staged as a lazy install for exactly:

```text
x86_64-delta_ag9032v2a-r0
```

Do not re-enable the full Delta module graph merely to fix V2A.

### Legacy transceiver plugins

```text
device/delta/x86_64-delta_ag9032v2a-r0/plugins/sfputil.py
device/delta/x86_64-delta_ag9032v2a-r0/plugins/eeprom.py
device/delta/x86_64-delta_ag9032v2a-r0/plugins/psuutil.py
```

`sfputil.py` should map logical port indices 0--32 to EEPROM buses 20--52 and
use the `delta-ag9032v2a-*` sysfs prefix. Plugin fixes normally affect optics
visibility, not creation of CONFIG_DB or APPL_DB port records.

## Phase 3: implementation rules by diagnosed layer

### If CONFIG_DB has no PORT records

Inspect `default_sku`, HWSKU directory naming, `port_config.ini`, and first-boot
config initialization. Do not modify kernel/I2C code.

### If syncd fails SAI initialization

Fix only the V2A `sai.profile` or V2A BCM file based on the first syncd error
and known-good hardware documentation. Do not suppress syncd failures and do
not switch to V2's non-premium profile.

### If platform service/module fails

Fix the V2A package, init script, service, or kernel module. Preserve buses
10--17 and 20--52. Validate unload/error cleanup as well as successful probe.

### If ports exist but SFPs are not detected

Fix only V2A module/sysfs/I2C/plugin mapping. Do not change `port_config.ini`
unless logical-to-physical evidence proves it is wrong.

## Manual verification after implementation

The agent must provide exact commands and wait for user results.

### Build package and image

```bash
make PLATFORM=broadcom \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb

SONIC_CONFIG_MAKE_JOBS=104 SONIC_BUILD_JOBS=32 NOBOOKWORM=1 \
  make target/sonic-broadcom.bin
```

### Inspect the platform deb

```bash
dpkg-deb -f target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb Depends
rm -rf /tmp/ag9032v2a-deb
dpkg-deb -x target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb /tmp/ag9032v2a-deb
modinfo /tmp/ag9032v2a-deb/lib/modules/6.12.41+deb13-sonic-amd64/extra/delta_ag9032v2a_platform.ko
```

### Hardware acceptance

- exactly 33 CONFIG_DB `PORT|*` records;
- exactly 33 expected logical front-panel interfaces;
- V2A platform service active;
- module vermagic matches `uname -r`;
- I2C buses 10--17 and 20--52 exist;
- 33 EEPROM paths exist;
- syncd and swss remain running;
- no SAI initialization errors;
- no V2 identifiers or non-premium profile paths are used;
- two controlled module unload/reload cycles complete without stale sysfs/I2C
  nodes, but only while dependent services are safely stopped.

## Final report

Report:

- observed hardware symptom and failing layer;
- evidence and first causal error;
- files and commits changed;
- why the fix preserves V2A identity and production behavior;
- package/image/manual hardware commands and user-provided results;
- unresolved risks or missing hardware documentation;
- rollback procedure.
