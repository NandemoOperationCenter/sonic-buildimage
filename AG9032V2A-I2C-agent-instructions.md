# AG9032V2A I2C and EEPROM topology investigation agent instructions

## Role

You are the investigation and implementation agent for the remaining
AG9032V2A platform I2C/EEPROM defect.

Repository:

```text
/mnt/nvme1/sonic-buildimage
```

The user performs package and image builds manually. You must first identify
the failing I2C layer from current-boot hardware evidence, then implement only
the narrowest proven fix.

If you need subagents, use GPT-5.6 Terra or Composer 2.5. Do not use another
subagent model. The primary agent remains responsible for validating all
subagent conclusions against source and hardware evidence.

## Mandatory reading

Read these files before starting:

```text
AG9032V2A-interface-investigation-agent-instructions.md
AG9032V2A-STAGE2-IMPLEMENTATION-REPORT.md
AG9032V2A-I2C-agent-instructions.md
```

Follow the Git, build, safety, V2/V2A separation, and evidence rules in the
main investigation instructions.

## Current known-good status

Stage 2 fixed Broadcom SAI initialization. The installed Stage 2 image on the
test chassis creates all 33 expected front-panel Ethernet interfaces.

Relevant successful Stage 2 commits include:

```text
26ca27bbf  select V2A premium Cancun b870.6.15.0
21da38868  use /sys/bus/i2c/devices for sfputil EEPROM lookup
bf8a7dfaf  enable common TD3 configuration inheritance
01878761f  align V2A memory initialization
c84f15c10  merge the Stage 2 result
```

Do not regress or modify the Stage 2 SAI/BCM solution as part of this task.

## Remaining symptom

On chassis `10.254.0.190`, the Stage 2 report recorded:

- all 33 Linux Ethernet interfaces exist;
- expected PCA9548 buses 10--17 are absent;
- expected transceiver buses 20--52 are absent;
- all 33 EEPROM paths are absent;
- `platform-modules-ag9032v2a.service` reports success;
- `pmon` is running.

This is a platform-module/I2C/optics problem independent of SAI interface
creation.

Prior observations were inconsistent: another OCP SONiC test had the complete
topology, while Enterprise SONiC used a different kernel/module stack. Treat
the current boot on `10.254.0.190` as the primary source of truth. Do not
assume the C module is defective before identifying the first kernel or service
error.

## Expected topology

The V2A contract is:

```text
parent adapter i2c-0
  -> CPLD mux child buses 1--3
  -> PCA9548 at bus 2 address 0x71
     -> fixed buses 10--17
  -> SWPLD mux on bus 3
     -> fixed buses 20--52
     -> EEPROM clients at address 0x50
```

Expected objects:

- 8 PCA9548 child adapters: 10--17;
- 33 transceiver adapters: 20--52;
- 33 readable EEPROM files;
- V2A sysfs prefix: `delta-ag9032v2a-*`;
- module: `delta_ag9032v2a_platform.ko`.

Do not substitute AG9032V2 identifiers, module names, sysfs paths, or the V2
PCA9548 implementation.

## Relevant source paths

```text
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/modules/delta_ag9032v2a_platform.c
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/scripts/ag9032v2a_platform_init.sh
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/cfg/ag9032v2a-modules.conf
platform/broadcom/sonic-platform-modules-delta/systemd/platform-modules-ag9032v2a.service
platform/broadcom/sonic-platform-modules-delta/debian/platform-modules-ag9032v2a.install
platform/broadcom/sonic-platform-modules-delta/debian/platform-modules-ag9032v2a.init
platform/broadcom/sonic-platform-modules-delta/debian/control
platform/broadcom/sonic-platform-modules-delta/debian/rules
platform/broadcom/platform-modules-delta-v2a.mk
platform/broadcom/one-image.mk
device/delta/x86_64-delta_ag9032v2a-r0/plugins/sfputil.py
```

AG9032V2 source may be read as a historical reference only. Do not copy V2
module names, profile paths, or kernel APIs into V2A.

## Source architecture to verify

In `delta_ag9032v2a_platform.c`, inspect at least:

- `delta_ag9032v2a_platform_init()`;
- `delta_pca9548_probe()`;
- `cpld_mux_probe()`;
- `swpld_mux_probe()`;
- `i2c_device_probe()`;
- all matching remove functions and error-unwind labels;
- constants for parent and fixed bus numbers.

The expected initialization order is:

1. register the local `delta-pca9548` driver;
2. register platform drivers;
3. create the CPLD client on parent adapter 0;
4. create fixed buses 1--3;
5. create `delta-pca9548` at bus 2/address `0x71`;
6. create fixed buses 10--17;
7. create SWPLD clients on bus 3;
8. create fixed buses 20--52;
9. create the ID EEPROM and 33 transceiver EEPROM clients.

Any registration failure should return non-zero and unwind all earlier
resources. Verify that the actual source still satisfies this behavior.

## Mandatory Git workflow

Before any edit:

1. Inspect root `git status`, staged and unstaged diffs, recent commits, and
   relevant submodule status.
2. Preserve every existing user change and generated artifact.
3. Never run `git reset`, `git restore`, `git clean`, or a destructive
   checkout.
4. Verify that current `master` contains the successful Stage 2 merge.
5. Create a focused implementation branch:

   ```text
   fix/ag9032v2a-i2c-topology
   ```

6. If the branch already exists, verify its base and changes before using it.
7. Stop if any eventual target file has unexpected staged or unstaged changes.
8. Commit each implementation change with a focused message. Do not amend or
   push.

Do not create the branch merely to collect read-only evidence if doing so
would interfere with existing work. The evidence gate comes before source
changes.

## Evidence gate: no implementation before diagnosis

Do not edit C, shell, service, packaging, or plugin files until you have:

1. collected current-boot evidence from `10.254.0.190`;
2. identified where the topology first disappears;
3. found the first relevant kernel, module, or service error; and
4. selected the matching narrow fix category below.

If evidence remains contradictory, perform the controlled reload experiment
after explicit user approval. Do not guess.

## Test chassis

Use:

```bash
ssh 10.254.0.190 -l tmcit -i ~/.ssh/sonic-builder
```

Use strict host-key verification. If the installed image changes the host key,
calculate the offered fingerprint and require independent user verification
before updating `known_hosts`. Never bypass verification or print private-key
contents.

Read-only hardware and log collection is allowed. Service restarts, module
load/unload, and chassis reboot require explicit user approval for this task.

## Phase 1: baseline evidence

Capture complete output. Use `sudo` only where available and required.

### A. Image, package, and module identity

```bash
sudo sonic-installer list
show version
uname -r
show platform summary
sonic-cfggen -H -v DEVICE_METADATA.localhost.platform

dpkg -l | grep -E 'platform-modules-ag9032v2a|linux-image'
dpkg -L platform-modules-ag9032v2a

sha256sum /lib/modules/$(uname -r)/extra/delta_ag9032v2a_platform.ko
modinfo delta_ag9032v2a_platform
modinfo -F vermagic delta_ag9032v2a_platform
strings /lib/modules/$(uname -r)/extra/delta_ag9032v2a_platform.ko |
  grep -E 'delta-pca9548|delta-ag9032v2a'
```

If `modinfo` or `strings` is unavailable, report that and continue. Do not
install packages.

### B. Service and loaded modules

```bash
lsmod | grep -E 'delta_ag9032|i2c_i801|i2c_mux|optoe'
systemctl status platform-modules-ag9032v2a.service --no-pager -l
sudo journalctl -u platform-modules-ag9032v2a.service -b --no-pager
sudo dmesg -T |
  grep -iE 'ag9032v2a|delta-pca9548|pca9548|swpld|cpld|i2c|optoe|failed|error|warn'
```

Find the first relevant current-boot line. Do not treat a later missing-EEPROM
message as the cause if an earlier mux or adapter error exists.

### C. Platform sysfs

```bash
ls -la /sys/devices/platform/ | grep delta-ag9032v2a
ls -la /sys/devices/platform/delta-ag9032v2a-cpld.0/ 2>/dev/null
ls -la /sys/devices/platform/delta-ag9032v2a-swpld1.0/ 2>/dev/null
cat /sys/devices/platform/delta-ag9032v2a-swpld1.0/sfp_is_present 2>/dev/null
```

### D. Adapter and mux inventory

```bash
ls -1 /sys/bus/i2c/devices/ | sort -V

for bus in 0 1 2 3 $(seq 10 17) $(seq 20 52); do
    if test -e "/sys/bus/i2c/devices/i2c-$bus"; then
        echo "present i2c-$bus"
    else
        echo "MISSING i2c-$bus"
    fi
done

ls -la /sys/bus/i2c/devices/i2c-2/ 2>/dev/null
ls -la /sys/bus/i2c/devices/2-0071/ 2>/dev/null
readlink -f /sys/bus/i2c/devices/2-0071/driver 2>/dev/null
```

### E. EEPROM and optoe

```bash
lsmod | grep optoe
modprobe -n optoe 2>&1

for bus in $(seq 20 52); do
    e="/sys/bus/i2c/devices/$bus-0050/eeprom"
    if test -r "$e"; then
        echo "OK $e"
    elif test -d "/sys/bus/i2c/devices/$bus-0050"; then
        echo "device without readable EEPROM bus $bus"
    elif test -d "/sys/bus/i2c/devices/i2c-$bus"; then
        echo "adapter without client bus $bus"
    else
        echo "MISSING adapter bus $bus"
    fi
done
```

### F. Preserve Stage 2 success

```bash
systemctl status syncd swss --no-pager
sonic-db-cli CONFIG_DB KEYS 'PORT|*' | wc -l
sonic-db-cli STATE_DB KEYS 'PORT_TABLE|*' | wc -l
show interface status
ip -br link
```

The I2C investigation must not regress the 33 Ethernet interfaces.

## Interpretation

Classify the failure before editing:

- module absent and service failed:
  - inspect the first `modprobe` or init error;
- loaded module lacks `delta-pca9548` strings:
  - wrong or stale package/image;
- buses 1--3 absent:
  - parent adapter or `cpld_mux_probe()` failure;
- bus 2 exists but `2-0071` does not:
  - PCA9548 client creation failure;
- `2-0071` exists but buses 10--17 do not:
  - `delta_pca9548_probe()` failure or fixed-bus collision;
- buses 10--17 exist but buses 20--52 do not:
  - SWPLD client or `swpld_mux_probe()` failure;
- buses 20--52 exist but EEPROM clients/files do not:
  - `optoe` loading or client binding problem;
- all kernel paths exist but userspace fails:
  - only then inspect `sfputil.py`.

The current init script validates only these SWPLD files:

```text
sfp_is_present
qsfp_lpmode
qsfp_reset
```

Service success therefore does not prove that all adapters and EEPROM clients
exist. Regardless of the primary fix, consider strengthening readiness checks
if hardware evidence confirms that the service can exit successfully with an
incomplete topology.

## Allowed fix categories

Choose only the category proven by Phase 1.

### Missing optoe only

If buses 20--52 exist but EEPROM clients/files are absent and `optoe` is not
loaded:

- add a checked `modprobe optoe` to the V2A init script;
- verify the module is packaged and available;
- add explicit EEPROM readiness checks;
- do not edit the C mux topology.

### Incomplete readiness checks

If the module creates the topology but the service can complete too early:

- update only `ag9032v2a_platform_init.sh`;
- verify buses 10--17 and 20--52;
- verify all 33 EEPROM clients/files when `optoe` is expected;
- fail visibly with a concise error identifying the first missing object;
- preserve `set -eu` and non-zero error propagation.

Use bounded loops only if the kernel needs a short asynchronous settle period.
Apply an explicit timeout and fail after it; never wait indefinitely.

### Parent adapter or ordering race

If logs show adapter 0, 2, or 3 is unavailable during init:

- fix only module/service ordering or bounded readiness waiting;
- do not assume module-level `-EPROBE_DEFER` will retry automatically;
- do not renumber adapters;
- preserve fixed bus numbers.

### PCA9548 or fixed-bus failure

If the first kernel error is in `delta_pca9548_probe()` or
`i2c_mux_add_adapter()`:

- modify only the V2A C module;
- preserve fixed buses 10--17;
- log the channel, requested bus number, and returned error;
- clean up every previously added adapter;
- return the original kernel error.

### SWPLD mux failure

If the first error is in SWPLD client or mux creation:

- modify only the corresponding V2A probe/error path;
- preserve buses 20--52;
- verify parent-client lifetime and teardown ordering;
- prevent partial-success return values.

### Wrong package or image

If runtime `.ko` content or version is stale:

- do not change source merely to force a build;
- correct the package/image rebuild and lazy-install process;
- inspect the deb and image before reinstalling.

## Forbidden changes

Do not modify:

- Stage 2 BCM memory settings;
- `common_config_support`;
- premium Cancun selection;
- `port_config.ini`;
- SAI profile or SAI/SDK packages;
- AG9032V2 files;
- bus numbers 10--17 or 20--52;
- V2A sysfs prefixes;
- sfputil mapping unless all kernel EEPROM paths exist and userspace alone is
  proven wrong;
- unrelated platform modules or common Delta code.

Do not add credentials, private keys, tokens, certificates, logs, cores, debs,
images, or generated output.

For C changes, do not introduce unbounded or unsafe memory/string functions.
Preserve explicit cleanup and original error propagation. Explain in the final
report how memory and string safety was maintained.

## Controlled reload experiment

Run only after baseline collection and explicit user approval.

Stop dependent services before unloading:

```bash
sudo systemctl stop pmon xcvrd 2>/dev/null || true
sudo systemctl stop platform-modules-ag9032v2a.service
```

Capture adapter, client, and sysfs inventory after stop. Confirm that no stale
V2A nodes remain.

Then start normally:

```bash
sudo systemctl start platform-modules-ag9032v2a.service
```

Repeat the complete module/service/I2C inventory. Perform two controlled cycles
to detect stale nodes, bus-number collisions, or cleanup defects.

Always restore `pmon`/`xcvrd` to their original state. If a command fails,
report the resulting state rather than masking the failure.

## Static verification after implementation

Without building:

1. Confirm the diff is limited to proven V2A files.
2. Run `git diff --check`.
3. Validate shell syntax with `bash -n` if a shell script changed.
4. Run applicable existing static checks without creating persistent output.
5. Check linter diagnostics.
6. Review all success, failure, and remove paths.
7. Confirm Stage 2 files and values are unchanged.
8. Confirm no generated or sensitive file is staged.

Commit the implementation as a focused commit. Do not push.

## Manual package and image build

The user performs builds.

For a platform-module, script, service, or packaging change, explicitly rebuild
the platform deb:

```bash
rm -f target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb

make PLATFORM=broadcom \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb
```

Inspect it before image build:

```bash
dpkg-deb -f \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb \
  Depends

rm -rf /tmp/ag9032v2a-i2c-deb
dpkg-deb -x \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb \
  /tmp/ag9032v2a-i2c-deb

modinfo \
  /tmp/ag9032v2a-i2c-deb/lib/modules/6.12.41+deb13-sonic-amd64/extra/delta_ag9032v2a_platform.ko

strings \
  /tmp/ag9032v2a-i2c-deb/lib/modules/6.12.41+deb13-sonic-amd64/extra/delta_ag9032v2a_platform.ko |
  grep -E 'delta-pca9548|delta-ag9032v2a'
```

If `modinfo` or `strings` is unavailable on the builder, report it and use
available package/file checks without installing tools.

Use a new build number:

```bash
rm -f target/sonic-broadcom.bin

BUILD_NUMBER=4 \
SONIC_CONFIG_MAKE_JOBS=104 \
SONIC_BUILD_JOBS=32 \
NOBOOKWORM=1 \
make target/sonic-broadcom.bin
```

Do not build or install unless the user explicitly asks. Provide commands and
wait for user results.

## Hardware acceptance

After the user installs the new image, verify:

- Stage 2 remains successful:
  - 33 CONFIG_DB front-panel ports;
  - 33 STATE_DB front-panel ports;
  - 33 Linux Ethernet interfaces;
  - syncd and swss active;
- platform service active with no causal errors;
- correct module loaded with matching vermagic;
- buses 1--3 exist;
- buses 10--17 exist;
- buses 20--52 exist;
- all 33 EEPROM clients/files exist and are readable;
- pmon/xcvrd do not report missing EEPROM paths;
- no V2 identifiers or non-premium profile paths appear;
- two controlled unload/reload cycles complete without stale nodes or bus
  collisions.

Do not equate interface creation with EEPROM success; verify both independently.

## Rollback

Provide a focused Git revert command for each implementation commit.

If a newly installed image prevents platform initialization:

1. boot the prior known-good Stage 2 image;
2. confirm the 33 Ethernet interfaces return;
3. revert only the I2C implementation commit;
4. do not revert the Stage 2 BCM/common-config commits.

## Mandatory completion report

Write the final report to:

```text
AG9032V2A-I2C-IMPLEMENTATION-REPORT.md
```

The report is mandatory even if implementation is unnecessary, hardware
verification fails, or the task is blocked.

Include:

- observed symptom and failing layer;
- exact first causal kernel/service error;
- baseline module, service, adapter, client, and EEPROM evidence;
- hypotheses ruled in and ruled out;
- branch and commit hashes;
- exact source diff;
- why the fix preserves V2A identity and topology;
- static verification;
- user-performed package/image commands and results;
- installed image version;
- Stage 2 regression checks;
- final bus and EEPROM counts;
- two-cycle reload results;
- acceptance result: PASS, FAIL, or BLOCKED;
- unresolved risks;
- exact rollback commands.

Do not include full logs, core dumps, credentials, private keys, tokens,
certificate bodies, licensed binaries, or proprietary package contents.
Include only minimal sanitized evidence.

Commit the report only if the user explicitly requests it or repository
instructions require it. Otherwise leave it as a clearly identified
uncommitted deliverable and report its path.

