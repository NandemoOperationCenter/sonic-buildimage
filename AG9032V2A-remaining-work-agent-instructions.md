# AG9032V2A/V2 remaining implementation and validation handoff

## Current state

The V2A-only Trixie package target now builds successfully:

```bash
make PLATFORM=broadcom \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb
```

The current worktree contains an uncommitted V2A Linux 6.12 port, staged
V2A-only build graph, Debian package updates, and systemd/helper updates.
Review all existing changes before modifying them.

## Mandatory workflow

1. **Create a new branch before making any additional implementation changes.**
   Branch from the current worktree state; do not discard or overwrite the
   existing uncommitted V2A work.
2. **Commit every additional implementation change** on that branch with a
   focused commit message. Do not amend unrelated commits.
3. **All builds are manual.** Do not start package, image, Docker, or hardware
   builds yourself. Provide the exact command and wait for the user to run it
   and share the result.
4. Do not commit generated files, temporary `dpkg/` directories,
   `sonic-slave-*/files/`, this handoff document, or any unrelated artifacts.

## Non-negotiable constraints

- Repository: `/mnt/nvme1/sonic-buildimage`
- Base commit: `9b0282489e36f24634e5f6e507cf53e7f9a6991a`
- Target: Linux `6.12.41+deb13-sonic-amd64`, Debian Trixie
- Never cherry-pick `remotes/origin/support-ag9032v2` commit `669ef79d1`.
- **Never edit `rules/config`.** It contains user-owned local changes.
- Do not copy V2's non-premium SAI profile to V2A.
- Do not silently convert V2 to premium. Keep V2's non-premium profile unless
  a separately approved design change is made after package and hardware proof.
- Keep each platform's ONIE name, HWSKU, sysfs prefix, module name, and BCM/SAI
  profile distinct.
- Keep the required I2C topology: PCA9548 buses 10--17 and transceiver buses
  20--52. Any mapping change requires a replacement mapping and hardware proof.
- Do not hardcode credentials, tokens, or keys. Do not add shell command-string
  construction. In C, do not add `sprintf()` or unbounded string/memory APIs.

## V2A work that remains

### 1. Inspect the built V2A deb

Ask the user to run the following against the resulting deb, then analyze the
output:

```bash
dpkg-deb -f <v2a-deb-path> Depends
dpkg-deb -c <v2a-deb-path>
dpkg-deb -x <v2a-deb-path> /tmp/ag9032v2a-deb
modinfo /tmp/ag9032v2a-deb/lib/modules/6.12.41+deb13-sonic-amd64/extra/delta_ag9032v2a_platform.ko
```

Acceptance:

- Depends resolves to the target `linux-image-6.12.41+deb13-sonic-amd64-unsigned`.
- The module is under `/lib/modules/6.12.41+deb13-sonic-amd64/extra/`.
- vermagic matches `6.12.41+deb13-sonic-amd64`.
- The package contains the helper invoked by systemd and the V2A systemd unit.

### 2. Validate V2A one-image integration

Verify that the staged V2A build graph and `one-image.mk` place the deb under
the lazy-install directory for exactly:

`x86_64-delta_ag9032v2a-r0`

Do not re-enable the original full `platform-modules-delta.mk` until every
affected Delta module is independently Linux 6.12 build-clean.

### 3. V2A systemd and hardware validation

The user must run hardware/image tests manually. Supply commands and interpret
results for:

- missing module, vermagic mismatch, and helper/readiness failure: systemd must
  fail and journal the cause; no leading `-` masking in `ExecStart`/`ExecStop`;
- service ordering before `pmon.service` and `xcvrd.service`;
- sysfs nodes;
- I2C buses 10--17 and 20--52;
- 33 EEPROMs and 33 logical PORT records;
- V2A premium SAI profile and running syncd;
- two module unload/reload cycles without stale nodes, reference leaks, or
  double unregister.

## V2 rollout: only after V2A passes

1. Port reviewed V2A kernel/package/systemd changes to V2 while retaining:
   - `x86_64-delta_ag9032v2-r0`
   - `Delta-ag9032v2`
   - `delta-ag9032v2-*` sysfs names
   - `delta_ag9032v2_platform.ko`
   - V2's non-premium BCM/SAI configuration
2. Add the V2 platform module explicitly to `platform/broadcom/one-image.mk`
   lazy installs.
3. Build V2 manually only after adding its isolated build registration or after
   all Delta modules are ported.
4. Require V2 package profile evidence and V2 hardware SAI initialization.
   If V2 hardware remains unavailable, report that as an explicit blocker; do
   not invent a premium fallback.

## Final report

Report:

- commits and files changed;
- manual commands and results;
- V2A package/image/systemd/hardware validation results;
- V2 validation status and blockers;
- unresolved issues;
- rollback: stop/disable the platform unit, stop dependent consumers, downgrade
  package and matching device data together, unload the module, or return to a
  known-good A/B image.
