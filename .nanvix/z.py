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

# Minimum byte size for ELF executables in integration checks, to guard
# against empty or truncated build outputs.
_MIN_EXECUTABLE_SIZE = 1000


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
        sysroot_p = self.translate_path(Path(sysroot))
        toolchain_p = self.translate_path(Path(toolchain))

        args = [
            "make", "-f", ".nanvix/Makefile.nanvix",
            f"{_MAKE_VAR_CONFIG}=y",
            f"{_MAKE_VAR_HOME}={sysroot_p}",
            f"{_MAKE_VAR_TOOLCHAIN}={toolchain_p}",
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

        On non-Windows, delegates to the Makefile (smoke + integration + functional).
        On Windows, runs test binaries from build/ via nanvixd.exe natively,
        following the same pattern as posix-tests and cpython.
        """
        if IS_WINDOWS:
            self._run_tests_windows()
            return
        targets = self.targets if self.targets else ["test"]
        self.run(*self._make_args(*targets), cwd=self.repo_root)

    def _run_tests_windows(self) -> None:
        """Run tests natively on Windows.

        - standalone: full functional tests executed via nanvixd.exe.
        - multi-process / single-process: integration checks only
          (linuxd is Linux-only; verify cross-compiled ELF executables are
          present and non-trivially sized to confirm successful compilation
          and linking).
        """
        if self.config.deployment_mode != "standalone":
            self._run_integration_checks_windows()
            return

        # --- standalone: full functional test via nanvixd.exe ---
        sysroot = self.config.get(CFG_SYSROOT, "")
        if not sysroot:
            log.fatal(f"{CFG_SYSROOT} is not set.", code=EXIT_MISSING_DEP, hint="Run `./z setup` first.")
        sysroot_path = Path(sysroot)
        nanvixd = sysroot_path / "bin" / "nanvixd.exe"
        mkramfs = sysroot_path / "bin" / "mkramfs.exe"
        if not nanvixd.is_file():
            log.fatal("nanvixd.exe not found.", code=EXIT_MISSING_DEP, hint="Run `./z setup` first.")
        if not mkramfs.is_file():
            log.fatal("mkramfs.exe not found.", code=EXIT_MISSING_DEP, hint="Run `./z setup` first.")

        # The Makefile outputs ELFs directly to the repository root, not to a
        # build/ subdirectory.  Search the repo root first; fall back to build/
        # for any future layout that moves outputs there.
        test_allowlist = {"example.elf"}
        test_binaries: list[Path] = []
        for candidate in [self.repo_root, self.repo_root / "build"]:
            if candidate.is_dir():
                elfs = sorted(candidate.glob("*.elf"))
                test_binaries = [b for b in elfs if b.name in test_allowlist]
                if test_binaries:
                    break

        if not test_binaries:
            print("No test binaries found in the repository -- smoke test only.")
            print("OK: no functional tests to run on Windows")
            return

        import shutil
        import tempfile
        failed = []
        for binary in test_binaries:
            name = binary.stem
            print(f"RUN  {name}...")
            with tempfile.TemporaryDirectory(prefix=f"nanvix_{name}_") as tmpdir:
                tmpdir_path = Path(tmpdir)
                ramfs_dir = tmpdir_path / "ramfs"
                ramfs_dir.mkdir()
                (ramfs_dir / "tmp").mkdir(exist_ok=True)
                shutil.copy2(binary, ramfs_dir / binary.name)
                # Write ramfs image alongside the ramfs source dir to avoid
                # self-inclusion while keeping artifacts scoped to this temp dir.
                ramfs_img = tmpdir_path / f"rootfs_{name}.img"
                try:
                    subprocess.run(
                        [str(mkramfs.resolve()), "-o", str(ramfs_img), str(ramfs_dir)],
                        check=True, timeout=60,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"FAIL {name} (mkramfs exit code {e.returncode})")
                    failed.append(name)
                    continue
                except subprocess.TimeoutExpired:
                    print(f"FAIL {name} (mkramfs timeout)")
                    failed.append(name)
                    continue
                try:
                    result = subprocess.run(
                        [str(nanvixd.resolve()), "-bin-dir", str((sysroot_path / "bin").resolve()),
                         "-ramfs", str(ramfs_img), "--", f"./{binary.name}"],
                        stdin=subprocess.DEVNULL, timeout=120,
                    )
                    if result.returncode != 0:
                        print(f"FAIL {name} (exit code {result.returncode})")
                        failed.append(name)
                    else:
                        print(f"OK   {name}")
                except subprocess.TimeoutExpired:
                    print(f"FAIL {name} (timeout)")
                    failed.append(name)

        if failed:
            msg = " ".join(failed)
            raise RuntimeError(f"{len(failed)} test(s) failed: {msg}")
        print(f"\t\t*** All {len(test_binaries)} tests PASSED ***")

    def _run_integration_checks_windows(self) -> None:
        """Integration artifact checks for non-standalone modes on Windows.

        Functional tests for multi-process and single-process modes require
        linuxd, which is Linux-only.  Instead, verify that the cross-compiled
        ELF executables are present and non-trivially sized, confirming
        successful compilation and static linking against the Nanvix sysroot.
        """
        mode = self.config.deployment_mode
        print(f"=== zlib Windows integration checks ({mode}) ===")
        print("  (Skipping functional tests: linuxd is not available on Windows)")

        failed: list[str] = []

        # Integration: cross-compiled test executables.
        required_elfs = {"example.elf", "minigzip.elf"}
        found: set[str] = set()
        for candidate in [self.repo_root, self.repo_root / "build"]:
            if candidate.is_dir():
                for elf_name in sorted(required_elfs - found):
                    elf = candidate / elf_name
                    if elf.is_file():
                        if elf.stat().st_size < _MIN_EXECUTABLE_SIZE:
                            print(f"  FAIL: {elf_name} too small ({elf.stat().st_size} bytes)")
                            failed.append(elf_name)
                        else:
                            print(f"  OK: {elf_name} ({elf.stat().st_size} bytes)")
                        found.add(elf_name)
        for missing in sorted(required_elfs - found):
            print(f"  FAIL: {missing} not found")
            failed.append(missing)

        if failed:
            raise RuntimeError(f"Integration checks failed: {' '.join(failed)}")
        print(f"\t\t*** Windows integration checks PASSED ({mode}) ***")

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
