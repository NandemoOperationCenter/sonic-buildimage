# AG9032V2A Stage 2 memory-profile A/B test agent instructions

## Role

You are the implementation agent for a controlled Stage 2 A/B test on the
Delta AG9032V2A.

The repository is:

```text
/mnt/nvme1/sonic-buildimage
```

The user performs all package and image builds manually. Your responsibilities
are to implement only the approved source change, commit it, provide exact
manual commands, inspect the resulting hardware after the user installs the
image, and write the final result to a Markdown report.

If you delegate any work to subagents, use only:

- GPT-5.6 Terra; or
- Composer 2.5.

Do not use any other subagent model. The primary agent remains responsible for
checking subagent findings against source and hardware evidence.

## Required reading

Read these files before doing anything:

```text
AG9032V2A-interface-investigation-agent-instructions.md
AG9032V2A-stage2-agent-instructions.md
```

Follow the safety, Git, build, V2/V2A separation, and evidence requirements in
the main investigation instructions. This Stage 2 document narrows the allowed
implementation further.

## Objective

Determine whether three memory-related BCM properties explain why Broadcom SAI
15.2 fails to create the switch on AG9032V2A after common TD3 configuration
inheritance has been enabled.

This is a controlled A/B test, not a general BCM configuration rewrite.

## Established evidence

### Current OCP SONiC test image

The image tested on `10.254.0.190` was:

```text
SONiC.fix_ag9032v2a-interface-init.2-bf8a7dfaf
```

It contained these prior fixes:

- `26ca27bbf`: select the V2A premium Cancun `b870.6.15.0`;
- `21da38868`: use `/sys/bus/i2c/devices/{bus}-0050/eeprom`;
- `bf8a7dfaf`: add the empty `common_config_support` platform marker.

Stage 1 worked as designed:

- the marker was present;
- `syncd_init_common.sh` merged the in-tree `b87` common TD3 configuration;
- `/tmp/sai.profile` selected the merged `/tmp/*.config.bcm`;
- common MMU, queue, tunnel, and capability properties were added;
- the V2A premium Cancun path, port maps, lane maps, polarity, and board values
  retained higher precedence.

However, SAI still failed:

```text
02:44:18.045783  switch create requested
02:44:19.847945  SAI_STATUS_FAILURE
```

Observed pipeline:

- CONFIG_DB ports: 33;
- Linux front-panel Ethernet interfaces: 0;
- swss failed after orchagent aborted;
- syncd became inactive as a downstream consequence.

### Known-good Enterprise SONiC baseline

The same platform successfully created all 33 front-panel interfaces under
Enterprise SONiC:

```text
SONiC-OS-4.2.0-Enterprise_Standard
libsaibcm 10.3.0.0
kernel 5.10.0-21-amd64
```

Its successful state included:

- CONFIG_DB ports: 33;
- STATE_DB ports: 33;
- Linux Ethernet interfaces: 33;
- ASIC_DB switches: 1;
- ASIC_DB ports: 37.

The V2A board-specific data was equivalent:

- all 33 `portmap_*` entries;
- both port bitmaps;
- all RX/TX lane maps;
- all RX/TX polarity values;
- `stable_size=0x5500000`;
- `module_64ports=1`;
- `port_flex_enable=1`;
- `bcm_num_cos=10`.

After the Stage 1 common merge, the remaining directly observed
memory-property differences are:

```diff
-parity_enable=0
-mem_cache_enable=0
+mem_cache_enable=1
-fpem_mem_entries=131072
+fpem_mem_entries=0
```

Common MMU properties such as `sai_optimized_mmu`,
`sai_mmu_tc_to_pg_config`, and the `buf.map.egress_pool*` mappings are already
provided by Stage 1. Do not duplicate or change them in Stage 2.

## Mandatory pre-edit workflow

Before editing:

1. Inspect root `git status`, staged and unstaged diffs, recent commits, and
   relevant submodule status.
2. Verify that the current branch contains:
   - `26ca27bbf`;
   - `21da38868`;
   - `bf8a7dfaf`.
3. Preserve every existing user change and generated artifact.
4. Never run `git reset`, `git restore`, `git clean`, or destructive checkout
   commands.
5. Create a focused Stage 2 branch from the current Stage 1 commit:

   ```text
   test/ag9032v2a-stage2-memory-profile
   ```

6. If that branch already exists, verify its base and contents before using it.
7. Stop and report if the target BCM file has unexpected staged or unstaged
   changes.

## Allowed implementation

Modify only:

```text
device/delta/x86_64-delta_ag9032v2a-r0/Delta-ag9032v2a/td3-ag9032v2a-32x100G+1x10G.config.bcm
```

Make exactly these changes:

```diff
-parity_enable=0
-mem_cache_enable=0
+mem_cache_enable=1
 l2_mem_entries=32768
 l3_mem_entries=16384
-fpem_mem_entries=131072
+fpem_mem_entries=0
```

Do not add replacement values for `parity_enable`; absence is intentional for
this A/B test.

Commit this source change as one focused commit. The message must explain that
the change aligns V2A memory initialization with the known-good effective
profile for a controlled SAI switch-create test. Do not amend or push.

## Files and values that must not change

Do not modify:

- `rules/config`;
- `port_config.ini`;
- `sai.profile`;
- `common_config_support`;
- `sfputil.py`;
- any AG9032V2 file;
- any platform kernel module or service;
- generic syncd or sairedis scripts;
- any common Broadcom configuration file;
- SAI/SDK binaries or package versions;
- the premium Cancun path;
- port maps, lane maps, polarity, bitmaps, speed, alias, or index mappings.

The following value must remain:

```text
sai_load_hw_config=/etc/bcm/flex/bcm56870_a0_premium_issu/b870.6.15.0/
```

Do not copy Enterprise SONiC binaries, Cancun packages, licensed content, or
proprietary package files into this repository or image.

## Static verification

Do not run image, package, Docker, or hardware builds.

Verify:

1. The Stage 2 branch diff changes only the one V2A BCM file.
2. The diff contains exactly:
   - deletion of `parity_enable=0`;
   - `mem_cache_enable=0` to `mem_cache_enable=1`;
   - `fpem_mem_entries=131072` to `fpem_mem_entries=0`.
3. `common_config_support` remains present and empty.
4. The premium Cancun path remains unchanged.
5. All `portmap_*`, lane-map, polarity, and bitmap lines are unchanged.
6. The BCM configuration checker passes if an already available checker can be
   run without building or creating persistent output.
7. `git diff --check` passes.
8. No credentials, keys, certificates, logs, cores, images, packages, or
   generated files are staged.

This task does not require C changes. Do not introduce any C string or memory
functions.

## Manual build handoff

The user performs builds. Provide these exact commands after committing:

```bash
rm -f target/debs/trixie/sonic-device-data_1.0-1_all.deb

make target/debs/trixie/sonic-device-data_1.0-1_all.deb
```

Before image build, instruct the user to extract and verify:

```bash
rm -rf /tmp/sonic-device-data-stage2
mkdir /tmp/sonic-device-data-stage2
dpkg-deb -x \
  target/debs/trixie/sonic-device-data_1.0-1_all.deb \
  /tmp/sonic-device-data-stage2

BCM=/tmp/sonic-device-data-stage2/usr/share/sonic/device/x86_64-delta_ag9032v2a-r0/Delta-ag9032v2a/td3-ag9032v2a-32x100G+1x10G.config.bcm

grep -E '^(parity_enable|mem_cache_enable|fpem_mem_entries|sai_load_hw_config)=' "$BCM"
test "$(grep -c '^parity_enable=' "$BCM")" -eq 0
grep -qx 'mem_cache_enable=1' "$BCM"
grep -qx 'fpem_mem_entries=0' "$BCM"
grep -qx 'sai_load_hw_config=/etc/bcm/flex/bcm56870_a0_premium_issu/b870.6.15.0/' "$BCM"
```

Use a build number newer than the installed Stage 1 image:

```bash
rm -f target/sonic-broadcom.bin

BUILD_NUMBER=3 \
SONIC_CONFIG_MAKE_JOBS=104 \
SONIC_BUILD_JOBS=32 \
NOBOOKWORM=1 \
make target/sonic-broadcom.bin
```

Wait for the user to build, install, and reboot. Do not perform those actions
unless the user explicitly asks.

## Hardware verification

The Stage 2 test chassis is:

```bash
ssh 10.254.0.190 -l tmcit -i ~/.ssh/sonic-builder
```

Treat SSH host keys as security-sensitive. If the image changes the host key,
calculate the offered fingerprint and require independent user verification
before updating `known_hosts`. Never bypass host-key checking.

After the user confirms installation, collect the complete current-boot
evidence.

### Confirm the image and effective configuration

```bash
sudo sonic-installer list
show version
uname -r
show platform summary

test -e /usr/share/sonic/platform/common_config_support
docker exec syncd grep -E \
  '^(parity_enable|mem_cache_enable|fpem_mem_entries|sai_load_hw_config)=' \
  /tmp/td3-ag9032v2a-32x100G+1x10G.config.bcm
```

Verify:

- build number is `3` or later;
- the common-config merge ran;
- `parity_enable` is absent;
- `mem_cache_enable=1`;
- `fpem_mem_entries=0`;
- the V2A premium Cancun path remains selected.

If the syncd container has already exited, inspect its mounted filesystem,
container logs, `/var/run/sswsyncd`, and host journal without modifying it.

### Port pipeline

```bash
sonic-db-cli CONFIG_DB KEYS 'PORT|*' | wc -l
sonic-db-cli APPL_DB KEYS 'PORT_TABLE:*' | wc -l
sonic-db-cli STATE_DB KEYS 'PORT_TABLE|*' | wc -l
sonic-db-cli ASIC_DB KEYS 'ASIC_STATE:SAI_OBJECT_TYPE_SWITCH:*' | wc -l
sonic-db-cli ASIC_DB KEYS 'ASIC_STATE:SAI_OBJECT_TYPE_PORT:*' | wc -l
show interface status
ip -br link
```

### Services and first causal error

```bash
systemctl status syncd swss --no-pager
docker ps -a | grep -E 'syncd|swss'
docker logs syncd 2>&1
docker logs swss 2>&1
sudo journalctl -u syncd -u swss -b --no-pager
```

Find the first current-boot BCM/SDK/SAI error. Do not report a later orchagent
abort as the root cause.

## Stage 2 acceptance criteria

Stage 2 passes only if all of these are true:

- syncd remains running;
- swss remains running;
- SAI switch creation succeeds;
- exactly one ASIC switch exists;
- expected ASIC port objects exist;
- all 33 expected front-panel Ethernet interfaces exist;
- CONFIG_DB, APPL_DB, and STATE_DB contain the expected port records;
- no V2 profile or non-premium profile is used;
- the common TD3 merge still occurs.

Operational link-down state without connected optics is acceptable. Missing
Linux Ethernet interfaces is not acceptable.

## Separate I2C issue

On the Stage 1 image, chassis `10.254.0.190` also lacked expected I2C buses
10--17 and 20--52 despite the platform service appearing active.

Treat that as a separate platform/optics defect. Do not modify platform module,
service, I2C, or sfputil code as part of Stage 2. First determine the Stage 2
SAI result. Record the I2C state as an unresolved independent issue in the
final report.

## Failure handling and rollback

If Stage 2 still returns `SAI_STATUS_FAILURE`:

1. Do not make additional speculative BCM changes.
2. Record whether the failure timestamp and stage changed.
3. Preserve the first causal current-boot error.
4. Report that the three memory properties are not sufficient.
5. Recommend the next experiment separately; do not implement it without new
   user approval.

Rollback is a focused revert of the Stage 2 commit. Do not revert the prior
Stage 1 marker, Cancun, or sfputil commits unless separately requested.

## Mandatory Markdown completion report

Write the completion report to:

```text
AG9032V2A-STAGE2-IMPLEMENTATION-REPORT.md
```

The report is mandatory even if Stage 2 fails or hardware verification is
blocked.

Include:

- objective and scope;
- branch and commit hashes;
- exact source diff;
- static verification;
- user-performed package/image commands and reported results;
- installed image version;
- effective merged BCM values;
- CONFIG_DB/APPL_DB/STATE_DB/ASIC_DB/Linux-interface counts;
- first causal SAI/SDK error or successful initialization sequence;
- acceptance result: PASS, FAIL, or BLOCKED;
- independent I2C issue status;
- risks and unresolved questions;
- exact rollback command.

Do not paste complete logs, core dumps, credentials, keys, certificates,
tokens, or proprietary binaries into the report. Include only minimal
sanitized evidence.

Commit the report only if repository instructions or the user explicitly
require it. Otherwise leave it as a clearly identified uncommitted
deliverable and report its path.

