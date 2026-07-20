# Investigate Broadcom image build test-environment failures

## Objective

Perform a read-only investigation of repeated failures while building:

```bash
make PLATFORM=broadcom SONIC_CONFIG_MAKE_JOBS=104 SONIC_BUILD_JOBS=32 target/sonic-broadcom.bin
```

Determine the systemic cause of Python wheel test failures in the build
container and recommend the smallest correct fixes. Do not make speculative
one-test-at-a-time changes.

The goal is for the normal Broadcom image build to complete while preserving
production behavior on a real SONiC device.

## Current failures

The current `error-log` contains at least these independent wheel failures:

### `sonic_utilities`

```text
target/python-wheels/trixie/sonic_utilities-1.2-py3-none-any.whl
ImportError while loading tests/conftest.py
utilities_common/chassis.py:is_smartswitch()
sonic_py_common/device_info.py:get_platform_json_data()
OSError: Failed to locate platform directory
```

The failure happens during test collection. `config/chassis_modules.py` creates
a Click choice using `is_smartswitch()`, which discovers device platform data
that does not exist in the package build container.

### `sonic_ycabled`

```text
target/python-wheels/trixie/sonic_ycabled-1.0-py3-none-any.whl
tests/test_y_cable_helper.py
AttributeError: 'NoneType' object has no attribute 'is_logical_port'
AttributeError: 'NoneType' object has no attribute 'get_presence'
```

`ycable/ycable_utilities/y_cable_helper.py` accesses the global
`y_cable_platform_sfputil` before it has been initialized. The log reports
many failures through the same missing initialization path, plus
`SystemExit: 2` in `DaemonYcable_init_deinit`.

### Earlier failures already addressed on the current branch

- Micas shared-output race: `cab92ea18`, `749e2a3f4`
- `sonic-config-engine` test container portability: `2e3f9b0d0`,
  `b9f672a0c`, `1309f066c`
- `sonic-platform-common` port-config fallback:
  submodule commit `6f3ee5b`, referenced by root commit `1dc8c5f9a`

Do not assume these changes are sufficient or correct without tracing their
call paths and package test environments.

## Mandatory workflow

1. Start by reviewing `git status --short --branch`, the full unstaged and
   staged diffs, recent commits, and submodule status. Preserve all existing
   worktree changes.
2. This is a read-only investigation. Do not edit files, create branches,
   commit, reset, clean, remove artifacts, or modify submodule revisions.
3. Do not run package, image, Docker, hardware, or full test-suite builds.
   The user runs builds manually. Do not use `make -B`, `make clean`, or remove
   build outputs.
4. Do not modify `rules/config`, AG9032V2A/V2 code, generated artifacts,
   temporary directories, logs, or unrelated submodules.
5. Treat `error-log` as evidence from the build container. Distinguish a
   package test setup defect from a production runtime defect before proposing
   any change.

## Investigation scope

Trace the complete path for each failure:

1. The image-level target and the corresponding wheel target/rules in the
   root build system.
2. Each package's `setup.py`, test invocation configuration, `pytest`
   configuration, environment variables, dependency installation, and working
   directory in the build container.
3. The source code that accesses device-specific state:
   - `src/sonic-utilities/tests/conftest.py`
   - `src/sonic-utilities/config/chassis_modules.py`
   - `src/sonic-utilities/utilities_common/chassis.py`
   - `src/sonic-py-common/sonic_py_common/device_info.py`
   - `src/sonic-platform-daemons/sonic-ycabled/ycable/ycable_utilities/y_cable_helper.py`
   - `src/sonic-platform-daemons/sonic-ycabled/tests/test_y_cable_helper.py`
   - `src/sonic-platform-common/sonic_platform_base/sonic_sfp/sfputilhelper.py`
4. How global objects, platform discovery, `PLATFORM`, mock fixtures, and
   test initialization are expected to work in production versus in a package
   test container.
5. All tests and call sites that share each failing global or platform lookup,
   so a single change cannot simply move the failure to another test.

Search broadly for:

```text
get_path_to_platform_dir
get_platform_json_data
is_smartswitch
y_cable_platform_sfputil
SfpUtilHelper
CFGGEN_UNIT_TESTING
PLATFORM
```

## Required analysis questions

For each failure, answer with exact files, functions, and call order:

1. Why does it require platform-specific state during a generic wheel test?
2. Is the expected correction in production code, test setup, package test
   configuration, or dependency/build-container setup?
3. Which behavior must remain unchanged on actual hardware?
4. What initialization or mock contract is missing?
5. What minimal change would cover every currently failing test in the same
   failure family?
6. What focused tests should be run by the user after implementation?

For the existing Micas and `sonic-config-engine` changes, also review whether
they are narrowly correct and identify any follow-up risk. Do not alter them.

## Deliverable

Return a concise evidence-backed report with:

- a failure matrix: wheel target, root cause, exact code path, and ownership;
- classification of each item as production bug, test bug, or packaging/test
  environment defect;
- a minimal implementation plan ordered by dependency and risk;
- files that would need changing, with a short rationale for each;
- focused manual verification commands, followed by the full image build
  command;
- blockers or uncertainties requiring a user decision.

Do not provide a patch or make changes in this investigation phase.
