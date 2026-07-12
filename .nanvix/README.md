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
| Compiler | `clang` |
| Archiver | `llvm-ar` |
| Ranlib | `llvm-ranlib` |
| Docker image | `ghcr.io/nanvix/nanvix-sdk-c-clang@sha256:f61737cb0780e6a2058c6d0bdf8ae5562db18de437173b2bcbbe6973abd3689f` |
| CFLAGS | `-O2 -Wall -D_GNU_SOURCE -msse2 -mfpmath=sse` |
| LDFLAGS | `-Wl,-z,noexecstack` |

The Makefile uses the Nanvix SDK at `NANVIX_TOOLCHAIN` (default `/opt/nanvix`).
The SDK compiler defaults to `i686-unknown-nanvix`.

### Build Outputs

| Artifact | Description |
| -------- | ----------- |
| `libz.a` | Static zlib library for Nanvix |
| `example.elf` | Comprehensive zlib test executable |
| `minigzip.elf` | Minimal gzip compression/decompression utility |

### Link Dependencies

All executables are linked through the SDK Clang driver against:

- `libz.a` — this library
- Nanvix libc and compiler runtime — from the SDK
- `crt0.o` and `user.ld` — selected by the SDK Clang driver

The downloaded Nanvix sysroot supplies runtime binaries only.

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
docker pull ghcr.io/nanvix/nanvix-sdk-c-clang@sha256:f61737cb0780e6a2058c6d0bdf8ae5562db18de437173b2bcbbe6973abd3689f

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
export NANVIX_TOOLCHAIN=/path/to/sdk         # Must contain nanvix-sdk.json and bin/clang
export NANVIX_HOME=/path/to/nanvix/sysroot   # Runtime binaries used by tests
make -f .nanvix/Makefile.nanvix CONFIG_NANVIX=y
```

## Make Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `CONFIG_NANVIX` | *(required)* | Must be set to enable Nanvix build (recommended `y`) |
| `NANVIX_HOME` | `$HOME/nanvix` | Path to Nanvix runtime binaries used by tests |
| `NANVIX_TOOLCHAIN` | `/opt/nanvix` | Path to the Nanvix SDK (must contain `nanvix-sdk.json`) |
| `CONFIG_NANVIX_DOCKER` | *(auto)* | Set to `y` to force Docker even when native toolchain exists |
| `NANVIX_DOCKER_IMAGE` | Nanvix c-clang SDK digest | Docker image for cross-compilation |
| `PLATFORM` | `unknown` | Target platform name (`microvm`) |
| `PROCESS_MODE` | `unknown` | Deployment mode (`standalone`) |
| `MEMORY_SIZE` | `unknown` | Memory configuration (`256mb`) |
| `PREFIX` | `$NANVIX_HOME` | Install prefix for `make install` |
| `DESTDIR` | *(empty)* | Staging directory prefix for `make install` |

## Make Targets

| Target | Description |
| ------ | ----------- |
| `all` | Build `libz.a` (default target) |
| `test` | Run all test levels (smoke + integration + functional) |
| `test-smoke` | Verify build artifacts exist and are valid (no runtime) |
| `test-integration` | Build and link test executables |
| `test-functional` | Execute `example.elf` on `nanvixd.elf` (requires KVM) |
| `package` | Create release tarball in `dist/` |
| `verify-package` | Validate the release tarball contents |
| `install` | Install library and headers to `PREFIX` |
| `clean` | Remove all build artifacts |

## Testing

Tests are organized in three levels:

1. **Smoke** (`test-smoke`) — Checks that `libz.a`, `zlib.h`, and `zconf.h` exist and that the library is non-trivially sized. No runtime environment needed.
2. **Integration** (`test-integration`) — Builds `example.elf` and `minigzip.elf`, verifying that they link successfully through the Nanvix SDK.
3. **Functional** (`test-functional`) — Runs `example.elf` inside the Nanvix runtime via `nanvixd.elf`. Requires KVM access. A RAM filesystem image is created with `mkramfs.elf` to provide `/tmp` for test file output.

Run specific levels:

```bash
./z test -- test-smoke test-integration
```

## Platform Configurations

Defined in `.nanvix/nanvix.toml` and used by CI:

| Axis | Values |
| ---- | ------ |
| Platform | `microvm` |
| Process mode | `standalone` |
| Memory size | `256mb` |

The microvm configuration is built and tested at 256 MB in CI. Nanvix
`v0.20.0` does not publish Hyperlight or 128 MB runtime assets.

## CI/CD

Workflow: `.github/workflows/nanvix-ci.yml`

Uses the reusable workflow `nanvix/workflows/.github/workflows/nanvix-ci.yml@v2.5.0`
with `nanvix-zutil` version `v0.14.0`.

| Trigger | Condition |
| ------- | --------- |
| Push | Branches matching `nanvix/**` |
| Pull request | Targeting branches matching `nanvix/**` |
| Schedule | Daily at 09:00 UTC |
| Manual | `workflow_dispatch` |

All platform configurations run in parallel with `fail-fast: false`.

## Limitations

- **Static linking only.** Shared libraries (`libz.so`) are not supported on Nanvix.
- **No `configure` step.** The upstream `./configure` script is not used. Build configuration is hardcoded in `.nanvix/Makefile.nanvix`.
- **KVM required for functional tests.** The `test-functional` target needs `/dev/kvm` access to run `nanvixd.elf`.
