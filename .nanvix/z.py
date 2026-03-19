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
import sysconfig
from pathlib import Path

_NANVIX_DIR = Path(__file__).resolve().parent
_VENV = _NANVIX_DIR / "venv"
_VENV_SCRIPTS = Path(
    sysconfig.get_path("scripts", vars={"base": str(_VENV), "platbase": str(_VENV)})
)
_VENV_PYTHON = _VENV_SCRIPTS / ("python.exe" if os.name == "nt" else "python")
_ZUTIL_RELEASE_URL = "https://github.com/nanvix/zutils/releases/download/v0.1.0-rc1/nanvix_zutil-0.1.0rc1-py3-none-any.whl"
_ZUTIL_HASH = "sha256:55df7a1ee81e401d6f9ead6a8e970c05599e3de7e66ff223a0186e5ad982d863"


def _inside_venv() -> bool:
    """Return True if already running inside the project venv."""
    if sys.prefix == sys.base_prefix:
        return False
    try:
        return Path(sys.executable).resolve().is_relative_to(_VENV.resolve())
    except (OSError, ValueError):
        return False


def _verify_and_install_wheel() -> None:
    """Download the nanvix-zutil wheel, verify its hash, and install it."""
    import hashlib
    import tempfile
    import urllib.request

    with tempfile.TemporaryDirectory() as tmpdir:
        whl_path = Path(tmpdir) / "nanvix_zutil.whl"
        print("bootstrap: downloading nanvix-zutil …", flush=True)
        urllib.request.urlretrieve(_ZUTIL_RELEASE_URL, whl_path)

        if _ZUTIL_HASH:
            algo, _, expected = _ZUTIL_HASH.partition(":")
            actual = hashlib.new(algo, whl_path.read_bytes()).hexdigest()
            if actual != expected:
                print(
                    f"error: hash mismatch for nanvix-zutil wheel\n"
                    f"  expected: {expected}\n"
                    f"  actual:   {actual}",
                    file=sys.stderr,
                )
                sys.exit(1)

        subprocess.check_call(
            [str(_VENV_PYTHON), "-m", "pip", "install", "-q", str(whl_path)]
        )


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
        _verify_and_install_wheel()


if not _inside_venv():
    if not _VENV_PYTHON.exists():
        _create_venv()
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
        if not tag:
            log.fatal("NANVIX_TAG is not set.", code=3)

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
