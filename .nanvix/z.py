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
from pathlib import Path

_NANVIX_DIR = Path(__file__).resolve().parent
_VENV_DIR = _NANVIX_DIR / "venv"
_ZUTIL_VERSION = "0.1.0"


def _bootstrap() -> None:
    """Ensure nanvix-zutil is installed in the local venv, then re-exec."""
    # Already running inside the venv — nothing to do.
    if sys.prefix != sys.base_prefix:
        return

    if not (_VENV_DIR / "pyvenv.cfg").exists():
        print(f"info: Creating virtual environment at {_VENV_DIR}", flush=True)
        subprocess.run(
            [sys.executable, "-m", "venv", str(_VENV_DIR)],
            check=True,
        )

    # Determine venv Python path (cross-platform).
    if sys.platform == "win32":
        venv_python = _VENV_DIR / "Scripts" / "python.exe"
    else:
        venv_python = _VENV_DIR / "bin" / "python"

    if not venv_python.exists():
        print(f"error: venv Python not found at {venv_python}", file=sys.stderr)
        sys.exit(3)

    # Install nanvix-zutil: from local path (dev) or PyPI (release).
    local_path = os.environ.get("NANVIX_ZUTIL_PATH")
    if local_path:
        pip_args = [str(venv_python), "-m", "pip", "install", "--quiet", "-e", local_path]
    else:
        pip_args = [
            str(venv_python), "-m", "pip", "install", "--quiet",
            f"nanvix-zutil=={_ZUTIL_VERSION}",
        ]

    subprocess.run(pip_args, check=True)

    # Re-exec under venv Python.
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


_bootstrap()

# ===== Build script (runs inside venv) =====

from nanvix_zutil import ZScript, Sysroot, log  # noqa: E402


class ZlibBuild(ZScript):
    """Build script for nanvix/zlib."""

    # zlib is a leaf library — no build-time dependencies.

    # Nanvix sysroot release tag. Override with NANVIX_TAG env var.
    NANVIX_TAG = "latest"

    def _make_args(self, *targets: str) -> list[str]:
        """Build the common make argument list."""
        sysroot = self.config.get("NANVIX_SYSROOT", "")
        toolchain = self.config.get("NANVIX_TOOLCHAIN", "/opt/nanvix")

        args = [
            "make", "-f", "Makefile.nanvix",
            "CONFIG_NANVIX=y",
            f"NANVIX_HOME={sysroot}",
            f"NANVIX_TOOLCHAIN={toolchain}",
        ]

        # Pass platform parameters when set.
        machine = self.config.machine
        mode = self.config.deployment_mode
        mem = self.config.memory_size
        args.extend([
            f"PLATFORM={machine}",
            f"PROCESS_MODE={mode}",
            f"MEMORY_SIZE={mem}",
        ])

        args.extend(targets)
        return args

    def setup(self) -> None:
        """Download the Nanvix sysroot."""
        tag = self.config.get("NANVIX_TAG", self.NANVIX_TAG)
        assert tag is not None

        sysroot = Sysroot.download(
            machine=self.config.machine,
            deployment_mode=self.config.deployment_mode,
            memory_size=self.config.memory_size,
            tag=tag,
            gh_token=self.config.get("GH_TOKEN"),
        )
        sysroot.verify(["lib/libposix.a", "lib/user.ld"])
        self.config.set("NANVIX_SYSROOT", str(sysroot.path))
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
