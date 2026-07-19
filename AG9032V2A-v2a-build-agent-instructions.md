# AG9032V2A V2A package build failure: investigation and fix

## Objective

Make the following V2A-only package target build successfully in the current
worktree:

```bash
make PLATFORM=broadcom \
  target/debs/trixie/platform-modules-ag9032v2a_1.1_amd64.deb
```

Do not broaden this task into a full Delta migration, one-image build, V2
rollout, hardware test, or SAI profile change.

## Baseline and constraints

- Repository: `/mnt/nvme1/sonic-buildimage`
- Branch: `master`
- Baseline commit: `9b0282489e36f24634e5f6e507cf53e7f9a6991a`
- Target kernel: `6.12.41+deb13-sonic-amd64`
- Do not cherry-pick `remotes/origin/support-ag9032v2` commit `669ef79d1`.
- Do not edit `rules/config`. It contains user-owned local changes and must
  remain byte-for-byte unchanged.
- Do not alter V2 files, platform/HWSKU/ONIE identifiers, BCM/SAI profiles,
  or `one-image.mk`.
- Do not commit, reset, restore, or delete unrelated generated files.
- Do not introduce credentials, tokens, keys, shell command string
  construction, `sprintf()`, or unbounded C string/memory APIs.

## Current staged V2A changes

The worktree deliberately enables only V2A through:

- `platform/broadcom/platform-modules-delta-v2a.mk`
- `platform/broadcom/platform-modules-delta-v2a.dep`
- `platform/broadcom/rules.mk`
- `platform/broadcom/rules.dep`

The original full `platform-modules-delta.mk` remains disabled because other
Delta modules have not yet been ported to Linux 6.12.

The V2A package source is:

`platform/broadcom/sonic-platform-modules-delta`

`debian/rules` intentionally builds only `ag9032v2a` in this staged phase.

## Observed failure

The package invocation reaches `dpkg-buildpackage`, but Make reports missing
prerequisites similar to:

```text
NON-EXISTENT PREREQUISITES:
target/debs/trixie/linux-headers-6.12.41+deb13-sonic-amd64_6.12.41-1_amd64.deb-install
target/debs/trixie/linux-headers-6.12.41+deb13-common-sonic_6.12.41-1_all.deb-install
```

An earlier packaging failure due to simultaneously declaring
`debian/compat` and `debhelper-compat (= 13)` has been addressed by removing
`debian/compat`. Verify that this remains correct, but focus on the missing
headers install targets.

The user has already run:

```bash
make PLATFORM=broadcom \
  target/debs/trixie/linux-headers-6.12.41+deb13-sonic-amd64_6.12.41-1_amd64.deb
```

Do not assume this made the prerequisite available. Establish the actual
target naming, dependency graph, output directory, and build-environment
selection from Make's expanded database and build logs.

## Required investigation

1. Reproduce the V2A package target failure once and capture the exact Make
   dependency graph. Use `make -pn`, `make -n`, and existing build logs before
   modifying build rules.
2. Compare the target/dependency declaration to an in-tree Trixie kernel
   module package that successfully depends on `$(LINUX_HEADERS)` and
   `$(LINUX_HEADERS_COMMON)`.
3. Determine whether the bug is:
   - incorrect outer target path,
   - BLDENV / configured distro mismatch,
   - package declaration ordering,
   - missing derived `-install` rule,
   - incorrect package destination (`trixie` vs another generated directory),
   - or a different build-system issue.
4. Make the minimal fix that preserves V2A-only staging and causes the headers
   prerequisites to be built/installed before `dpkg-buildpackage`.
5. Run the exact V2A target above. If it succeeds, inspect the resulting deb:

```bash
dpkg-deb -f <deb> Depends
dpkg-deb -c <deb>
modinfo <extracted-ko>
```

Confirm dependency, module install path, and vermagic all target
`6.12.41+deb13-sonic-amd64`.

## Acceptance criteria

- The V2A deb target completes successfully.
- Only V2A module source is compiled during this staged build.
- Header dependencies are resolved by the build graph, not manually copied.
- `debian/compat` is not present when `debhelper-compat` is used.
- No changes to `rules/config`, V2, profiles, or one-image configuration.
- Report exact changed files, commands/results, and any remaining blockers.
