# zlib for Nanvix

<!-- METADATA
project: zlib
upstream-url: https://zlib.net/
upstream-repo: https://github.com/madler/zlib
upstream-version: 1.3.1
target-os: Nanvix
target-arch: i686
nanvix-version: 0.12.420
build-system: GNU Make
output-type: static library
license: zlib/libpng (see LICENSE)
-->

## Summary

This repository is a port of the **zlib 1.3.1** compression library to the **Nanvix** operating system. Nanvix is a POSIX-compatible educational OS targeting the i686 architecture. The port cross-compiles zlib into a static library (`libz.a`) and two test executables (`example.elf`, `minigzip.elf`), with no source-level changes to zlib's compression logic.

## Repository Layout

All Nanvix-specific files live under `.nanvix/` or in the repository root as thin wrappers. The zlib source tree is otherwise unmodified from upstream 1.3.1.

```text
.nanvix/
├── Makefile.nanvix    # Cross-compilation Makefile (primary build file)
├── README.md          # This file
├── nanvix.toml        # Package manifest (name, version, build matrix)
└── z.py               # Python build script (extends nanvix-zutil ZScript)

Root wrappers:
├── z                  # Entry point (detects OS, delegates to z.sh or z.ps1)
├── z.sh               # Bash wrapper — bootstraps nanvix-zutil, then delegates
└── z.ps1              # PowerShell wrapper — same behavior on Windows

CI:
└── .github/workflows/nanvix-ci.yml   # GitHub Actions workflow
```

## Source Changes from Upstream

Exactly **one** source file was modified:

| File | Change | Reason |
| ---- | ------ | ------ |
| `gzguts.h` | Added `#include <unistd.h>` inside `#ifndef _WIN32` guard | Nanvix requires explicit include for POSIX I/O functions (`lseek`, `read`, `write`, `close`) |

No other `.c` or `.h` files were modified. The compression algorithms, public API (`zlib.h`, `zconf.h`), and all upstream tests are identical to zlib 1.3.1.

## Build System

### Toolchain

| Component | Value |
| --------- | ----- |
| Compiler | `clang --target=i686-unknown-nanvix` |
| Linker | `clang` (drives `ld.lld`) |
| Archiver | `llvm-ar` |
| Ranlib | `llvm-ranlib` |
| Docker image | `ghcr.io/nanvix/llvm-project:ca7933e47d3a` |
| CFLAGS | `--target=i686-unknown-nanvix -march=pentiumpro -O2 -Wall` |
| LDFLAGS | `--target=i686-unknown-nanvix -Wl,-z,noexecstack -Wl,-z,muldefs -Wl,-T,user.ld -Wl,--entry=_do_start` |

The toolchain is the Nanvix LLVM toolchain, with `clang` configured for the native `i686-unknown-nanvix` target. clang uses the toolchain's Nanvix sysroot for system headers and, at link time, automatically pulls in the startup object (`crt0.o`), the C/math libraries and the compiler-rt builtins. Only the Nanvix-specific link bits are supplied explicitly: the guest linker script (`-T user.ld`), the crt0 entry point (`--entry=_do_start`), and `-z muldefs` (crt0.o and libc.a share some low-level objects). The Makefile auto-detects the toolchain. If the native cross-compiler is not found at `NANVIX_TOOLCHAIN` (default `/opt/nanvix`), it falls back to Docker automatically.

### Build Outputs

| Artifact | Description |
| -------- | ----------- |
| `libz.a` | Static zlib library for Nanvix |
| `example.elf` | Comprehensive zlib test executable |
| `minigzip.elf` | Minimal gzip compression/decompression utility |

### Link Dependencies

Executables are statically linked. clang resolves the following from the toolchain sysroot automatically; only `libz.a` is supplied by this build:

- `libz.a` — this library
- `crt0.o` — process startup (entry `_do_start`), from the toolchain sysroot
- `libc.a` — from the toolchain sysroot
- `libm.a` — from the toolchain sysroot
- `libclang_rt.builtins-i386.a` — compiler-rt builtins, from the toolchain sysroot
- `user.ld` — guest linker script, from the toolchain sysroot at `$NANVIX_TOOLCHAIN/lib/`


## Quick Start

### Option A: Using nanvix-zutil (recommended)

```bash
# The ./z wrapper auto-bootstraps nanvix-zutil 0.7.19 into .nanvix/venv/ on first run.
# Requires: python3
./z setup    # Downloads Nanvix sysroot
./z build    # Cross-compiles libz.a
./z test     # Runs smoke + integration + functional tests
./z clean    # Removes build artifacts
./z release  # Packages release tarball into dist/
```

Override the pinned nanvix-zutil version with `NANVIX_ZUTIL_VERSION=<version>`.

### Option B: Direct Make with Docker

```bash
# Pull the Docker image
docker pull ghcr.io/nanvix/llvm-project:ca7933e47d3a

# Download Nanvix sysroot
curl -fsSL https://raw.githubusercontent.com/nanvix/nanvix/refs/heads/dev/scripts/get-nanvix.sh \
  | bash -s -- nanvix-artifacts
tar -xjf nanvix-artifacts/*microvm*single*.tar.bz2 -C nanvix-artifacts
export NANVIX_HOME=$(find nanvix-artifacts -maxdepth 2 -type d -name "bin" -exec dirname {} \; | head -1)

# Build
make -f .nanvix/Makefile.nanvix CONFIG_NANVIX=y NANVIX_HOME="$NANVIX_HOME"

# Test
make -f .nanvix/Makefile.nanvix CONFIG_NANVIX=y NANVIX_HOME="$NANVIX_HOME" test
```

### Option C: Native toolchain (no Docker)

```bash
export NANVIX_TOOLCHAIN=/path/to/toolchain   # Must contain bin/clang and lib/user.ld
export NANVIX_HOME=/path/to/nanvix/sysroot   # Runtime sysroot (bin/nanvixd.elf) used by `test`
make -f .nanvix/Makefile.nanvix CONFIG_NANVIX=y
```

## Make Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `CONFIG_NANVIX` | *(required)* | Must be set to enable Nanvix build (recommended `y`) |
| `NANVIX_HOME` | `$HOME/nanvix` | Path to Nanvix runtime sysroot (provides `bin/nanvixd.elf` for `test`) |
| `NANVIX_TOOLCHAIN` | `/opt/nanvix` | Path to cross-compiler (must contain `bin/clang` and `lib/user.ld`) |
| `CONFIG_NANVIX_DOCKER` | *(auto)* | Set to `y` to force Docker even when native toolchain exists |
| `NANVIX_DOCKER_IMAGE` | `ghcr.io/nanvix/llvm-project:ca7933e47d3a` | Docker image for cross-compilation |
| `PLATFORM` | `unknown` | Target platform name (`microvm`, `hyperlight`) |
| `PROCESS_MODE` | `unknown` | Deployment mode (`standalone`) |
| `MEMORY_SIZE` | `unknown` | Memory configuration (`256mb`) |
| `PREFIX` | `$NANVIX_HOME` | Install prefix for `make install` |
| `DESTDIR` | *(empty)* | Staging directory prefix for `make install` |

## Make Targets

| Target | Description |
| ------ | ----------- |
| `all` | Build `libz.a` and the test executables (default target) |
| `test` | Run functional test checks (the standalone run is driven by `./z test`) |
| `test-functional` | Stub for `make test`; `./z test` drives the standalone run |
| `package` | Create release tarball in `dist/` |
| `verify-package` | Validate the release tarball contents |
| `install` | Install library and headers to `PREFIX` |
| `clean` | Remove all build artifacts |

## Testing

Only the `standalone` deployment mode is supported. `./z test` runs the
standalone functional test: it boots `example.elf` inside the Nanvix runtime via
`nanvixd.elf`, bundling it with the guest daemons in an initrd and providing a
RAM filesystem (`mkramfs.elf`) for the test's file output. The test asserts a
guest exit code of 0 and requires KVM access on Linux.

Alongside it, the build itself covers two cheaper levels: a **smoke** check that
`libz.a`, `zlib.h`, and `zconf.h` are produced, and an **integration** check
that `example.elf` and `minigzip.elf` link against the Nanvix toolchain.

## Platform Configurations

Defined in `.nanvix/nanvix.toml` and used by CI:

| Axis | Values |
| ---- | ------ |
| Platform | `hyperlight`, `microvm` |
| Process mode | `standalone` |
| Memory size | `256mb` |

All combinations (2 x 1 x 1 = 2) are built and tested in CI.

## CI/CD

Workflow: `.github/workflows/nanvix-ci.yml`

Uses the reusable workflow `nanvix/workflows/.github/workflows/nanvix-ci.yml@v1.7.6` with `nanvix-zutil` version `v0.7.19`.

| Trigger | Condition |
| ------- | --------- |
| Push | Branches matching `nanvix/**` |
| Pull request | Targeting branches matching `nanvix/**` |
| Schedule | Daily at 09:00 UTC |
| Manual | `workflow_dispatch` |

All 2 platform configurations run in parallel with `fail-fast: false`.

## Limitations

- **Static linking only.** Shared libraries (`libz.so`) are not supported on Nanvix.
- **No `configure` step.** The upstream `./configure` script is not used. Build configuration is hardcoded in `.nanvix/Makefile.nanvix`.
- **KVM required for functional tests.** The `test-functional` target needs `/dev/kvm` access to run `nanvixd.elf`.
