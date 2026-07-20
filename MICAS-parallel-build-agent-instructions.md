# Fix Micas shared-output build failure blocking V2A image validation

## Goal

Fix the unrelated Micas package build failure that blocks creation of
`target/sonic-broadcom.bin`. The fix must make the Micas package deterministic
under parallel `make` execution.

Do not change AG9032V2A/V2 code unless it is directly required to validate the
Micas fix.

## Known failure

The full Broadcom image build failed while building:

```text
target/debs/trixie/platform-modules-micas-m2-w6510-48v8c_1.0_amd64.deb
```

The first real error is:

```text
cp: cannot create regular file \
'/sonic/platform/broadcom/sonic-platform-modules-micas/common/app/build/app':
No such file or directory
```

This occurs in:

```text
platform/broadcom/sonic-platform-modules-micas/common/app/fw_upgrade/fw_upgrade
```

The log shows that other Micas sub-builds run concurrently, and
`dev_util` later copies successfully to this same shared output directory.
`hw_test_driver` itself compiled successfully; it is not the root cause. The
malformed Debian changelog trailer is only a warning.

`common/app/Makefile` already declares `build/app` and `build/module` as
order-only prerequisites for its subdirectory targets. However, the
`fw_upgrade/fw_upgrade` Makefile copies its output without first creating the
destination, while `dev_util` and `hw_test_app` create it themselves. The
failure establishes a missing-output-directory defect, but does not by itself
prove why the parent order-only prerequisite was not effective in this run.

Determine that cause before editing. The required fix must make normal
parallel builds deterministic, rather than relying on serial build execution.

## Mandatory workflow

1. Review `git status`, the existing diff, and relevant Micas Makefiles before
   modifying anything.
2. Create a new branch before implementation changes. Preserve all current
   worktree changes.
3. Commit every implementation change with a focused commit message.
4. Do not start package, image, Docker, or hardware builds. All builds are run
   manually by the user. Provide exact commands and wait for results.
5. Do not edit `rules/config`.
6. Do not modify, revert, or expand the AG9032V2A/V2 work.
7. Do not commit generated artifacts, build output, temporary directories, or
   logs.

## Scope

Primary files to inspect:

```text
platform/broadcom/sonic-platform-modules-micas/common/app/Makefile
platform/broadcom/sonic-platform-modules-micas/common/app/fw_upgrade/Makefile
platform/broadcom/sonic-platform-modules-micas/common/app/fw_upgrade/fw_upgrade/Makefile
platform/broadcom/sonic-platform-modules-micas/common/app/dev_util/Makefile
platform/broadcom/sonic-platform-modules-micas/common/app/hw_test/Makefile
platform/broadcom/sonic-platform-modules-micas/debian/rules
platform/broadcom/sonic-platform-modules-micas/debian/rule.mk
```

Identify every producer that copies into shared paths such as:

```text
common/app/build/app
common/app/build/module
```

Trace how `common_out_put_dir` reaches each recursive submake and why the
existing parent-level directory prerequisite did not protect the failing copy.
Then implement the narrowest correct solution. Each producer copying to a
shared output directory must ensure that directory exists in its own target,
or have an explicit, effective dependency on a directory target.

The result must remain correct under parallel execution and must not rely on
timing between recursive makes. Do not treat `-j1` as a fix.

Prefer a narrow Makefile-only fix. Do not disable Micas packages, remove them
from the Broadcom build graph, or change the global build parallelism.

## Verification

After the code change, provide these manual commands for the user:

```bash
git status --short
make PLATFORM=broadcom target/debs/trixie/platform-modules-micas-m2-w6510-48v8c_1.0_amd64.deb
make PLATFORM=broadcom target/sonic-broadcom.bin
```

Do not run them yourself.

## Final report

Report:

- root cause with exact file/target;
- files changed and commit hash;
- why the dependency/order fix is parallel-safe;
- manual commands and user-provided results;
- any remaining blockers to the V2A image validation.
