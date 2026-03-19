# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Nanvix build script for zlib.

Usage:
    ./z setup     # Download Nanvix sysroot
    ./z build     # Cross-compile libz.a
    ./z test      # Run test suite (smoke + integration + functional)
    ./z release   # Package release tarball
    ./z clean     # Remove build artifacts
"""

# ===== Self-bootstrapping preamble (stdlib only) =====
# Creates .nanvix/venv/, installs nanvix-zutil, re-execs under venv Python.

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

_NANVIX_DIR = Path(__file__).resolve().parent
_VENV = _NANVIX_DIR / "venv"
_VENV_PYTHON = _VENV / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
_ZUTIL_TAG = "v0.1.0-rc2"
_ZUTIL_RELEASE_BASE = "https://github.com/nanvix/zutils/releases/download"
_ZUTIL_HASH = "sha256:728a6ac6c9265ce58727569156c21877f94dbf6b449849a28585ccc6cde1b91f"


def _inside_venv() -> bool:
    """Return True if already running inside the project venv."""
    return sys.prefix != sys.base_prefix


def _create_venv() -> None:
    """Create the venv and install nanvix-zutil."""
    print("bootstrap: creating venv …", flush=True)
    subprocess.check_call([sys.executable, "-m", "venv", str(_VENV)])
    local_path = os.environ.get("NANVIX_ZUTIL_PATH")
    if local_path:
        print("bootstrap: installing nanvix-zutil (editable) …", flush=True)
        subprocess.check_call(
            [str(_VENV_PYTHON), "-m", "pip", "install", "-q", "-e", local_path]
        )
    else:
        version = _ZUTIL_TAG.lstrip("v").replace("-", "")
        whl_name = f"nanvix_zutil-{version}-py3-none-any.whl"
        whl_url = f"{_ZUTIL_RELEASE_BASE}/{_ZUTIL_TAG}/{whl_name}"
        req_line = f"nanvix_zutil @ {whl_url} --hash={_ZUTIL_HASH}"
        print(f"bootstrap: installing nanvix-zutil ({_ZUTIL_TAG}) …", flush=True)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(req_line + "\n")
            req_path = f.name
        try:
            subprocess.check_call(
                [str(_VENV_PYTHON), "-m", "pip", "install", "-q",
                 "--require-hashes", "-r", req_path]
            )
        finally:
            Path(req_path).unlink(missing_ok=True)


if not _inside_venv():
    if not _VENV_PYTHON.exists():
        _create_venv()
    rc = subprocess.call(
        [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]]
    )
    sys.exit(rc)

# ===== Build script (runs inside venv) =====

from nanvix_zutil import ZScript, Sysroot, log  # noqa: E402

# Make variable names passed to Makefile.nanvix.
_MAKE_VAR_CONFIG = "CONFIG_NANVIX"
_MAKE_VAR_HOME = "NANVIX_HOME"
_MAKE_VAR_TOOLCHAIN = "NANVIX_TOOLCHAIN"
_MAKE_VAR_PLATFORM = "PLATFORM"
_MAKE_VAR_PROCESS_MODE = "PROCESS_MODE"
_MAKE_VAR_MEMORY_SIZE = "MEMORY_SIZE"

# Config keys.
_CFG_SYSROOT = "NANVIX_SYSROOT"
_CFG_TOOLCHAIN = "NANVIX_TOOLCHAIN"
_CFG_TAG = "NANVIX_TAG"
_CFG_GH_TOKEN = "GH_TOKEN"

# Sysroot verification files.
_SYSROOT_REQUIRED_FILES = ["lib/libposix.a", "lib/user.ld"]


class ZlibBuild(ZScript):
    """Build script for nanvix/zlib."""

    # zlib is a leaf library — no build-time dependencies.

    # Nanvix sysroot release tag. Override with NANVIX_TAG env var.
    NANVIX_TAG = "latest"

    def _make_args(self, *targets: str) -> list[str]:
        """Build the common make argument list."""
        self.config.load()
        sysroot = self.config.get(_CFG_SYSROOT, "")
        if not sysroot:
            log.fatal(
                f"{_CFG_SYSROOT} is not set.",
                code=3,
                hint="Run `./z setup` first to download the sysroot.",
            )
        toolchain = self.config.get(_CFG_TOOLCHAIN, "/opt/nanvix")

        args = [
            "make", "-f", "Makefile.nanvix",
            f"{_MAKE_VAR_CONFIG}=y",
            f"{_MAKE_VAR_HOME}={sysroot}",
            f"{_MAKE_VAR_TOOLCHAIN}={toolchain}",
        ]

        # Pass platform parameters when set.
        machine = self.config.machine
        mode = self.config.deployment_mode
        mem = self.config.memory_size
        args.extend([
            f"{_MAKE_VAR_PLATFORM}={machine}",
            f"{_MAKE_VAR_PROCESS_MODE}={mode}",
            f"{_MAKE_VAR_MEMORY_SIZE}={mem}",
        ])

        args.extend(targets)
        return args

    def setup(self) -> None:
        """Download the Nanvix sysroot."""
        tag = self.config.get(_CFG_TAG, self.NANVIX_TAG)
        if not tag:
            log.fatal(f"{_CFG_TAG} is not set.", code=3)

        sysroot = Sysroot.download(
            machine=self.config.machine,
            deployment_mode=self.config.deployment_mode,
            memory_size=self.config.memory_size,
            tag=tag,
            gh_token=self.config.get(_CFG_GH_TOKEN),
        )
        sysroot.verify(_SYSROOT_REQUIRED_FILES)
        self.config.set(_CFG_SYSROOT, str(sysroot.path))
        self.config.save()
        log.success("Setup complete")

    def build(self) -> None:
        """Cross-compile libz.a for Nanvix."""
        self.config.load()
        self.run(*self._make_args("all"), cwd=self.repo_root)
        log.success("Build complete")

    def test(self) -> None:
        """Run the zlib test suite (smoke + integration + functional)."""
        self.config.load()
        self.run(*self._make_args("test"), cwd=self.repo_root)
        log.success("Tests passed")

    def release(self) -> None:
        """Package the zlib release tarball."""
        self.config.load()
        self.run(*self._make_args("package"), cwd=self.repo_root)
        log.success("Release packaged")

    def clean(self) -> None:
        """Remove build artifacts."""
        self.run(
            "make", "-f", "Makefile.nanvix", "clean",
            cwd=self.repo_root,
        )
        log.success("Clean complete")


if __name__ == "__main__":
    ZlibBuild.main()
