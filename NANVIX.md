# zlib Port for Nanvix

> **TL;DR:** This is a port of the zlib compression library for the Nanvix operating system. Jump to [Quick Start](#quick-start) to get started immediately.

---

## Overview

This document describes the port of [zlib](https://zlib.net/) compression library for the [Nanvix](https://github.com/nanvix/nanvix) operating system. This port enables zlib to run on Nanvix, a POSIX-compatible educational operating system.

| Property | Value |
|----------|-------|
| **Base Version** | zlib 1.3.1 |
| **Target Platform** | Nanvix (i686) |
| **Build System** | `./z` (ZScript) |

**What's included:**
- ✅ Cross-compilation support for Nanvix
- ✅ Static library build (`libz.a`)
- ✅ Test executables (`example.elf`, `minigzip.elf`)
- ✅ Build helper scripts
- ✅ CI/CD integration

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Building](#building)
4. [Testing](#testing)
5. [Changes Summary](#changes-summary)
6. [Known Limitations](#known-limitations)
7. [CI/CD](#cicd)

---

## Quick Start

For experienced users who want to build quickly:

```bash
# 1. Set up Nanvix sysroot (downloads toolchain + sysroot automatically)
./z setup

# 2. Build
./z build

# 3. Run tests (smoke + integration)
./z test -- smoke integration

# 4. Package release tarball
./z release
```

Continue reading for detailed instructions.

---

## Prerequisites

You need two components to build zlib for Nanvix:

| Component | Description | Default Location |
|-----------|-------------|------------------|
| **Nanvix Toolchain** | i686-nanvix cross-compiler | `$HOME/toolchain` |
| **Nanvix Sysroot** | System libraries and linker script | `$HOME/nanvix` |

Both are downloaded automatically by `./z setup`.

### Available Platform Configurations

| Platform | Process Mode | Artifact Pattern |
|----------|--------------|------------------|
| hyperlight | multi-process | `hyperlight.*multi-process` |
| hyperlight | single-process | `hyperlight.*single-process` |
| microvm | single-process | `microvm.*single-process` |
| microvm | multi-process | `microvm.*multi-process` |

---

## Building

### Using Docker (Recommended)

The `./z` wrapper supports automatic Docker fallback via `--with-docker`:

```bash
# Build with Docker (toolchain container used automatically)
./z build --with-docker
```

### Using Native Toolchain

```bash
# Set up sysroot first
./z setup

# Build
./z build
```

### Build Outputs

After a successful build, you will have:

| File | Description |
|------|-------------|
| `libz.a` | zlib static library |
| `example.elf` | zlib example/test executable |
| `minigzip.elf` | Minimal gzip utility |

---

## Testing

> **Important:** Functional tests run through the Nanvix daemon (`nanvixd.elf`).

### Running the Test Suite

```bash
# Run all tests (smoke + integration + functional)
./z test

# Run specific test levels
./z test -- smoke integration
./z test -- functional
```

### Test Levels

| Level | Description |
|-------|-------------|
| `smoke` | Verify `libz.a` and headers exist and are non-trivial |
| `integration` | Build and link `example.elf` and `minigzip.elf` |
| `functional` | Run `example.elf` via `nanvixd.elf` (requires KVM) |

---

## Changes Summary

The following changes were made to support Nanvix.

### Build System

| Change | Description |
|--------|-------------|
| Build orchestration | All build logic in `.nanvix/z.py` via `./z` commands |
| Cross-compilation | Uses `i686-nanvix-gcc` from the Nanvix toolchain |
| Docker support | Transparent Docker wrapping via `--with-docker` |
| Linker flags | Nanvix-specific flags (`-T user.ld -static`) |
| Shared libraries | Disabled (not supported on Nanvix) |

### New Files

| File | Purpose |
|------|---------|
| `.nanvix/z.py` | Build script (ZScript subclass) |
| `.nanvix/nanvix.toml` | Package manifest |
| `z` / `z.ps1` | Bootstrap wrappers |
| `NANVIX.md` | This documentation file |
| `.github/workflows/nanvix-ci.yml` | CI workflow for automated builds |

### Source Code Changes

| File | Change |
|------|--------|
| `gzguts.h` | Added `#include <unistd.h>` for POSIX I/O declarations (`lseek`, `read`, `write`, `close`) |

---

## Known Limitations

| Limitation | Impact |
|------------|--------|
| **No shared libraries** | Only static library (`libz.a`) is built |
| **Static linking only** | All executables are statically linked |

---

## CI/CD

The GitHub Actions workflow at `.github/workflows/nanvix-ci.yml` automates building and testing on every change.

### Trigger Events

| Event | Description |
|-------|-------------|
| Push to `nanvix/**` | Any push to Nanvix branches |
| PR to `nanvix/**` | Pull requests targeting Nanvix branches |
| Daily schedule | Runs at midnight UTC |
| Manual dispatch | Can be triggered manually |
| Repository dispatch | Triggered by `nanvix-release` events |

### Build Matrix

The CI runs on 4 different platform/process-mode configurations:

| Platform | Process Mode | Runner |
|----------|--------------|--------|
| hyperlight | multi-process | `self-hosted-hyperlight-multi` |
| hyperlight | single-process | `self-hosted-hyperlight-single` |
| microvm | single-process | `self-hosted-microvm-single` |
| microvm | multi-process | `self-hosted-microvm-multi` |

All configurations run in parallel with `fail-fast: false`, ensuring that all platforms are tested even if one fails.

---
