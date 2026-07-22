# AG9032V2A I2C readiness race fix agent instructions

## Role

You are the implementation agent for the final AG9032V2A platform-service
readiness race.

Repository:

```text
/mnt/nvme1/sonic-buildimage
```

The user performs package and image builds manually. Your task is to implement
one bounded readiness wait, commit it, provide manual build commands, verify
the rebuilt image after the user installs it, and update the existing I2C
implementation report.

If you need subagents, use GPT-5.6 Terra or Composer 2.5. Do not use another
subagent model. Validate subagent conclusions against source and hardware
evidence before acting on them.

## Mandatory reading

Read these files before starting:

```text
AG9032V2A-interface-investigation-agent-instructions.md
AG9032V2A-I2C-agent-instructions.md
AG9032V2A-I2C-IMPLEMENTATION-REPORT.md
AG9032V2A-I2C-readiness-agent-instructions.md
```

Follow all Git, build, V2/V2A separation, security, and evidence rules from the
earlier instructions.

## Established evidence

The installed image is:

```text
SONiC-OS-master.5-140194d91
Kernel: 6.12.41+deb13-sonic-amd64
Platform: x86_64-delta_ag9032v2a-r0
HwSKU: Delta-ag9032v2a
```

The source fixes are package-owned and present in the image. They successfully
provide:

- `i2c_smbus.disable_spd=Y` from boot;
- no conflicting root SPD clients;
- buses 1--3;
- buses 10--17;
- buses 20--52;
- 33 transceiver clients;
- 33 readable EEPROM paths;
- running `xcvrd`;
- populated `TRANSCEIVER_INFO`;
- 33 Linux front-panel Ethernet interfaces;
- active syncd and swss.

No current-boot errors remain for:

- EEPROM address `-EBUSY`;
- `get_transceiver_change_event` signature mismatch;
- `KeyError('vendor_rev')`;
- xcvrd fatal processing.

However, on two consecutive cold boots the platform service exited with status
1 just before asynchronous EEPROM client registration completed. The topology
and optics became healthy moments later.

The current script performs immediate readiness tests:

```bash
for bus in {20..52}; do
    test -r "/sys/bus/i2c/devices/${bus}-0050/eeprom"
done
```

This creates a deterministic service-status race: a valid asynchronous kernel
registration can finish after the first failed `test`.

## Objective

Replace only the immediate 33-path check with a bounded, polling readiness
wait.

Requirements:

1. Success when all 33 EEPROM paths become readable.
2. Poll at a bounded interval without busy-spinning.
3. Enforce an explicit overall timeout.
4. Return non-zero after timeout.
5. Print one concise error containing the missing bus numbers.
6. Preserve `set -eu`.
7. Do not hide module, sysfs, or EEPROM failures.
8. Do not wait indefinitely.

Recommended defaults:

```text
timeout: 30 seconds
poll interval: 0.2 seconds
expected buses: 20--52
```

The implementation may use equivalent values only if current-boot timing
evidence justifies them. Document any deviation.

## Mandatory Git workflow

Before editing:

1. Inspect root `git status`, staged and unstaged diffs, recent commits, and
   relevant submodule status.
2. Preserve all user changes and generated artifacts.
3. Never run `git reset`, `git restore`, `git clean`, or destructive checkout.
4. Verify that `master` contains merge `140194d91`.
5. Create a focused branch:

   ```text
   fix/ag9032v2a-i2c-readiness
   ```

6. If it already exists, verify its base and contents.
7. Stop if the target script has unexpected changes.
8. Commit the source fix with a focused message. Do not amend or push.

## Allowed source change

Modify only:

```text
platform/broadcom/sonic-platform-modules-delta/ag9032v2a/scripts/ag9032v2a_platform_init.sh
```

Add a small helper such as:

```text
wait_for_eeproms
```

The helper should:

- build a fresh list of missing buses during each poll;
- return immediately when the list is empty;
- use a monotonic shell elapsed-time mechanism such as Bash `SECONDS`;
- sleep between polls;
- print missing bus numbers only on final timeout;
- return failure to the existing `set -e` caller.

Replace the immediate loop with one call to the helper after:

```bash
modprobe "$PLATFORM_MODULE"
```

Keep the existing SWPLD readiness checks. Do not move the EEPROM wait before
the platform module is loaded.

## Required behavior sketch

This is a behavior requirement, not a mandatory byte-for-byte implementation:

```bash
wait_for_eeproms()
{
    local deadline=$((SECONDS + EEPROM_READY_TIMEOUT_SECONDS))
    local bus
    local -a missing_buses

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
```

Review Bash `set -u` behavior for all arrays and variables. Ensure the helper
works correctly when the missing list is empty or contains all 33 buses.

## Forbidden changes

Do not modify:

- the V2A kernel C module;
- `ag9032v2a-params.conf`;
- package install manifests;
- `sfputil.py`;
- Stage 2 BCM memory settings;
- `common_config_support`;
- premium Cancun selection;
- `port_config.ini` or `sai.profile`;
- AG9032V2 files;
- bus numbers or EEPROM addresses;
- pmon, xcvrd, syncd, or swss source;
- common Delta or Broadcom scripts.

Do not add credentials, private keys, tokens, certificates, logs, cores,
packages, images, or generated output.

No C code should change. If scope unexpectedly expands to C, stop and obtain
new user approval rather than introducing memory/string operations.

## Static verification

Do not build packages, images, or Docker artifacts.

Verify:

1. `bash -n` passes for the modified script.
2. `git diff --check` passes.
3. The branch diff changes only the one V2A init script.
4. The previous SPD suppression and safe module reload logic are unchanged.
5. The existing SWPLD checks remain.
6. The wait is bounded and sleeps between polls.
7. The final timeout returns non-zero and names missing buses.
8. Success requires all 33 EEPROM paths.
9. Stage 2 BCM and interface files are unchanged.
10. No generated or sensitive file is staged.

Use a temporary-directory or isolated shell harness to exercise:

- all paths immediately present;
- paths appearing after a short delay;
- permanent missing paths causing timeout;
- multiple missing bus numbers in the error.

Do not alter real `/sys` during static testing. Remove temporary test files
afterward.

Check IDE diagnostics after editing.

## Commit

Commit only the source script change. Use a message that explains the reason,
for example:

```text
wait for ag9032v2a EEPROM topology readiness
```

Do not commit the final report until hardware verification is complete and the
user requests or repository workflow requires the documentation commit.

## Manual platform package build

The user performs the build.

Because this script is packaged in the platform deb, force its rebuild:

```bash
rm -f target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb

make PLATFORM=broadcom \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb
```

Extract and verify:

```bash
rm -rf /tmp/ag9032v2a-readiness-deb
dpkg-deb -x \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb \
  /tmp/ag9032v2a-readiness-deb

SCRIPT=/tmp/ag9032v2a-readiness-deb/usr/local/bin/ag9032v2a_platform_init.sh

bash -n "$SCRIPT"
grep -nE 'wait_for_eeproms|EEPROM_READY|timed out' "$SCRIPT"
```

The `sonic-device-data` package does not require rebuilding for this isolated
script change unless source evidence shows it changed. Do not rebuild
unrelated packages.

## Manual image build

Use a build number newer than build 5:

```bash
rm -f target/sonic-broadcom.bin

BUILD_NUMBER=6 \
SONIC_CONFIG_MAKE_JOBS=104 \
SONIC_BUILD_JOBS=32 \
NOBOOKWORM=1 \
make target/sonic-broadcom.bin
```

Wait for the user to build, install, and cold boot. Do not run builds or install
the image yourself unless explicitly requested.

## Test chassis and SSH safety

Use:

```bash
ssh 10.254.0.190 -l tmcit -i ~/.ssh/sonic-builder
```

Use strict host-key verification. A new image may change the host key. If it
does, calculate the offered fingerprint and require independent user
verification before updating `known_hosts`. Never bypass verification.

## Installed-image cold-boot acceptance

After user installation, collect:

```bash
sudo sonic-installer list
show version
uptime
uname -r
show platform summary

systemctl status platform-modules-ag9032v2a.service --no-pager -l
sudo journalctl -u platform-modules-ag9032v2a.service -b --no-pager

cat /sys/module/i2c_smbus/parameters/disable_spd
```

Verify the platform script is package-owned and unmodified:

```bash
dpkg -S /usr/local/bin/ag9032v2a_platform_init.sh
dpkg --verify platform-modules-ag9032v2a
stat /usr/local/bin/ag9032v2a_platform_init.sh
```

Verify topology:

```bash
for bus in 1 2 3 $(seq 10 17) $(seq 20 52); do
    test -e "/sys/bus/i2c/devices/i2c-$bus" ||
        echo "MISSING i2c-$bus"
done

for bus in $(seq 20 52); do
    test -r "/sys/bus/i2c/devices/$bus-0050/eeprom" ||
        echo "MISSING EEPROM bus $bus"
done
```

Verify services and Stage 2:

```bash
systemctl status pmon syncd swss --no-pager
docker exec pmon supervisorctl status xcvrd
sonic-db-cli CONFIG_DB KEYS 'PORT|*' | wc -l
sonic-db-cli STATE_DB KEYS 'PORT_TABLE|*' | wc -l
show interface status
ip -br link
```

Verify at least one inserted optic:

```bash
sonic-db-cli STATE_DB HGETALL 'TRANSCEIVER_INFO|Ethernet20'
show interfaces transceiver presence Ethernet20
show interfaces transceiver eeprom Ethernet20
```

Adapt the interface only if the populated module is in a different port.

## Acceptance criteria

All must pass:

- platform service is active/successful after cold boot;
- journal shows the bounded wait completed without timeout;
- `disable_spd=Y`;
- no root SPD client blocks mux addresses;
- buses 1--3, 10--17, and 20--52 exist;
- all 33 EEPROM paths are readable;
- xcvrd is running;
- optics are detected;
- CONFIG_DB, STATE_DB, and Linux have all 33 front-panel interfaces;
- syncd and swss are active;
- no current-boot `-EBUSY`, change-event `TypeError`, or `vendor_rev` `KeyError`;
- package verification shows no hot-updated target file.

## Two controlled installed-image reload cycles

Run only after explicit user approval.

Record the original pmon/xcvrd state. Stop dependent consumers before each
platform-service restart:

```bash
sudo systemctl stop pmon
sudo systemctl stop platform-modules-ag9032v2a.service
```

After stop, verify:

- V2A platform nodes are absent;
- buses 1--3 are absent;
- buses 10--17 are absent;
- buses 20--52 are absent;
- no transceiver clients remain.

Then:

```bash
sudo systemctl start platform-modules-ag9032v2a.service
```

Verify service success and the complete topology before restoring pmon:

```bash
sudo systemctl start pmon
```

Perform exactly two cycles. Ensure pmon is restored even if a cycle fails.
Report, do not mask, any stale node, collision, timeout, or service failure.

## Failure handling

If the bounded wait times out:

1. capture the missing buses from the script error;
2. capture the first kernel/module error;
3. do not increase the timeout blindly;
4. determine whether topology creation actually failed rather than merely
   completing slowly;
5. stop before making further source changes.

If topology succeeds but the service remains failed, capture the exact command
and exit status. Do not suppress the failure.

## Rollback

Provide the exact source commit hash and:

```bash
git revert <readiness-fix-commit>
```

If the new image regresses platform initialization, boot build 5, which
preserves functional optics despite the service-status race.

Do not revert the SPD suppression, V2A plugin compatibility, Stage 2 BCM, or
common-config fixes.

## Mandatory report update

Update:

```text
AG9032V2A-I2C-IMPLEMENTATION-REPORT.md
```

Do not merely append a contradictory result. Reconcile and replace stale
sections.

At minimum:

1. Record the new source commit and merged commit if applicable.
2. Correct the previous `git diff --check` claim and remove trailing
   whitespace.
3. Replace build-5 FAIL/BLOCKED language with actual build-6 evidence.
4. Clearly distinguish earlier hot tests from installed-image tests.
5. Record package provenance and verification.
6. Record cold-boot platform-service status.
7. Record bus, EEPROM, interface, and optics counts.
8. Record the bounded-wait duration or immediate success.
9. Record both installed-image reload cycles.
10. Update board-ID `1-0053` as present and root-readable.
11. Set final result to PASS, FAIL, or BLOCKED based on all criteria.
12. Include risks and exact rollback.

Do not include full logs, credentials, keys, tokens, certificates, core dumps,
packages, images, or proprietary binaries. Include only minimal sanitized
evidence.

Commit the report separately only after final hardware verification and only
if the user requests or repository workflow requires it.

