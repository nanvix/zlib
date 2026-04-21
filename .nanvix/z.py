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

import subprocess
import sys
from pathlib import Path

from nanvix_zutil import CFG_SYSROOT, CFG_TOOLCHAIN, EXIT_MISSING_DEP, ZScript, log

IS_WINDOWS = sys.platform == "win32"

# Makefile variable names (build-system-specific).
_MAKE_VAR_CONFIG = "CONFIG_NANVIX"
_MAKE_VAR_HOME = "NANVIX_HOME"
_MAKE_VAR_TOOLCHAIN = "NANVIX_TOOLCHAIN"
_MAKE_VAR_PLATFORM = "PLATFORM"
_MAKE_VAR_PROCESS_MODE = "PROCESS_MODE"
_MAKE_VAR_MEMORY_SIZE = "MEMORY_SIZE"


class ZlibBuild(ZScript):
    """Build script for nanvix/zlib."""

    def _make_args(self, *targets: str) -> list[str]:
        """Build the common make argument list."""
        sysroot = self.config.get(CFG_SYSROOT, "")
        if not sysroot:
            log.fatal(
                f"{CFG_SYSROOT} is not set.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z setup` first to download the sysroot.",
            )
        toolchain = self.config.get(CFG_TOOLCHAIN, "/opt/nanvix")

        args = [
            "make", "-f", ".nanvix/Makefile.nanvix",
            f"{_MAKE_VAR_CONFIG}=y",
            f"{_MAKE_VAR_HOME}={sysroot}",
            f"{_MAKE_VAR_TOOLCHAIN}={toolchain}",
        ]

        args.extend([
            f"{_MAKE_VAR_PLATFORM}={self.config.machine}",
            f"{_MAKE_VAR_PROCESS_MODE}={self.config.deployment_mode}",
            f"{_MAKE_VAR_MEMORY_SIZE}={self.config.memory_size}",
        ])

        args.extend(targets)
        return args

    def setup(self) -> None:
        """Download the Nanvix sysroot."""
        super().setup()

    def build(self) -> None:
        """Cross-compile libz.a for Nanvix."""
        self.run(*self._make_args("all"), cwd=self.repo_root)

    def test(self) -> None:
        """Run the zlib test suite.

        On Linux, delegates to the Makefile (smoke + integration + functional).
        On Windows, runs test binaries from build/ via nanvixd.exe natively,
        following the same pattern as posix-tests and cpython.
        """
        if IS_WINDOWS:
            self._run_tests_windows()
            return
        targets = self.targets if self.targets else ["test"]
        self.run(*self._make_args(*targets), cwd=self.repo_root)

    def _run_tests_windows(self) -> None:
        """Run tests natively on Windows using nanvixd.exe.

        Expects test binaries (.elf) in build/ (downloaded from the Linux
        CI build artifact by the reusable workflow). Runs each test binary
        in a standalone VM via nanvixd.exe + mkramfs.exe.
        """
        sysroot = self.config.get(CFG_SYSROOT, "")
        if not sysroot:
            log.fatal(
                f"{CFG_SYSROOT} is not set.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z setup` first.",
            )
        sysroot_path = Path(sysroot)
        nanvixd = sysroot_path / "bin" / "nanvixd.exe"
        mkramfs = sysroot_path / "bin" / "mkramfs.exe"
        if not nanvixd.is_file():
            log.fatal(
                "nanvixd.exe not found in sysroot.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z setup` to download Windows host binaries.",
            )

        build_dir = self.repo_root / "build"
        test_binaries = sorted(build_dir.glob("*.elf")) if build_dir.is_dir() else []

        if not test_binaries:
            # No test binaries — smoke test only (verify library was built).
            print("No test binaries found in build/ — smoke test only.")
            release_dir = self.repo_root / "dist"
            tarballs = list(release_dir.glob("*.tar.bz2")) if release_dir.is_dir() else []
            if tarballs:
                print(f"OK: release tarball found ({tarballs[0].name})")
            else:
                print("OK: no test binaries to run (library-only repo)")
            return

        # Run each test binary in a standalone VM.
        import tempfile
        failed = []
        for binary in test_binaries:
            name = binary.stem
            print(f"RUN  {name}...")

            # Build a minimal ramfs with the test binary.
            ramfs_dir = Path(tempfile.mkdtemp(prefix=f"nanvix_{name}_"))
            (ramfs_dir / "tmp").mkdir(exist_ok=True)
            import shutil
            shutil.copy2(binary, ramfs_dir / binary.name)

            ramfs_img = ramfs_dir / "rootfs.img"
            subprocess.run(
                [str(mkramfs.resolve()), "-o", str(ramfs_img), str(ramfs_dir)],
                check=True, capture_output=True,
            )

            try:
                result = subprocess.run(
                    [str(nanvixd.resolve()), "-bin-dir", str((sysroot_path / "bin").resolve()),
                     "-ramfs", str(ramfs_img), "--", str(binary.name)],
                    stdin=subprocess.DEVNULL,
                    timeout=120,
                )
                if result.returncode != 0:
                    print(f"FAIL {name} (exit code {result.returncode})")
                    failed.append(name)
                else:
                    print(f"OK   {name}")
            except subprocess.TimeoutExpired:
                print(f"FAIL {name} (timeout)")
                failed.append(name)
            finally:
                shutil.rmtree(ramfs_dir, ignore_errors=True)

        if failed:
            raise RuntimeError(
                f"{len(failed)} test(s) failed: {' '.join(failed)}"
            )
        print(f"\t\t*** All {len(test_binaries)} tests PASSED ***")

    def release(self) -> None:
        """Package the zlib release tarball and verify it."""
        self.run(*self._make_args("package"), cwd=self.repo_root)
        self.run(*self._make_args("verify-package"), cwd=self.repo_root)

    def clean(self) -> None:
        """Remove build artifacts."""
        self.run(
            "make", "-f", ".nanvix/Makefile.nanvix", "clean",
            cwd=self.repo_root,
        )


if __name__ == "__main__":
    ZlibBuild.main()
