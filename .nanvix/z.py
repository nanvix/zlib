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
_VENV = _NANVIX_DIR / "venv"
_VENV_PYTHON = _VENV / ("Scripts" if os.name == "nt" else "bin") / "python"
_ZUTIL_VERSION = "0.1.0"
# TODO: Replace with actual GitHub release URL once available.
_ZUTIL_RELEASE_URL = ""

if not sys.prefix.startswith(str(_VENV)):
    if not _VENV.exists():
        print("bootstrap: creating venv …", flush=True)
        subprocess.check_call([sys.executable, "-m", "venv", str(_VENV)])
        print("bootstrap: installing nanvix-zutil …", flush=True)
        local_path = os.environ.get("NANVIX_ZUTIL_PATH")
        if local_path:
            subprocess.check_call(
                [str(_VENV_PYTHON), "-m", "pip", "install", "-q", "-e", local_path]
            )
        elif _ZUTIL_RELEASE_URL:
            subprocess.check_call(
                [str(_VENV_PYTHON), "-m", "pip", "install", "-q", _ZUTIL_RELEASE_URL]
            )
        else:
            print(
                "error: NANVIX_ZUTIL_PATH not set and release URL is not configured.",
                file=sys.stderr,
            )
            sys.exit(3)
    rc = subprocess.call(
        [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]]
    )
    sys.exit(rc)

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
