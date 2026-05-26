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

import sys
from pathlib import Path

from nanvix_zutil import (
    CFG_SYSROOT,
    EXIT_MISSING_DEP,
    TOOLCHAIN_CONTAINER_PATH,
    ZScript,
    log,
    make_initrd,
    run,
)
from nanvix_zutil.helpers import InitRdArgs

IS_WINDOWS = sys.platform == "win32"

#: Docker image for cross-compiling Nanvix targets.
NANVIX_DOCKER_IMAGE = "ghcr.io/nanvix/toolchain-gcc:sha-34a3641"

# Makefile variable names (build-system-specific).
_MAKE_VAR_HOME = "NANVIX_HOME"
_MAKE_VAR_TOOLCHAIN = "NANVIX_TOOLCHAIN"
_MAKE_VAR_PLATFORM = "PLATFORM"
_MAKE_VAR_PROCESS_MODE = "PROCESS_MODE"
_MAKE_VAR_MEMORY_SIZE = "MEMORY_SIZE"


class ZlibBuild(ZScript):
    """Build script for nanvix/zlib."""

    def docker_image(self) -> str:
        """Return the default Docker image for cross-compilation."""
        return NANVIX_DOCKER_IMAGE

    def _make_args(self, *targets: str) -> list[str]:
        """Build the common make argument list.

        Path translation for ``NANVIX_HOME`` is applied when running
        under Docker (i.e. ``self.docker`` is set).  Recipes that
        execute purely on the host receive the raw host path.
        """
        sysroot = self.config.get(CFG_SYSROOT, "")
        if not sysroot:
            log.fatal(
                f"{CFG_SYSROOT} is not set.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z setup` first to download the sysroot.",
            )
        sysroot_p = (
            self.docker.translate_path(Path(sysroot)) if self.docker else Path(sysroot)
        )

        args = [
            "make",
            "-f",
            ".nanvix/Makefile.nanvix",
            f"{_MAKE_VAR_HOME}={sysroot_p}",
            f"{_MAKE_VAR_TOOLCHAIN}={TOOLCHAIN_CONTAINER_PATH}",
            f"{_MAKE_VAR_PLATFORM}={self.config.machine}",
            f"{_MAKE_VAR_PROCESS_MODE}={self.config.deployment_mode}",
            f"{_MAKE_VAR_MEMORY_SIZE}={self.config.memory_size}",
        ]

        args.extend(targets)
        return args

    def setup(self) -> bool:
        """Download the Nanvix sysroot."""
        return super().setup()

    def build(self) -> None:
        """Cross-compile libz.a for Nanvix."""
        run(*self._make_args("all"), cwd=self.repo_root, docker=self.docker)

    def test(self) -> None:
        """Run the zlib test suite.

        Smoke and integration tests are always delegated to the Makefile.
        The functional test in standalone mode is handled in Python via
        make_initrd so that initrd creation is shared across platforms.
        """
        if IS_WINDOWS:
            self._run_tests_windows()
            return

        if self.config.deployment_mode == "standalone":
            # Smoke + integration via Makefile (host-side; recipes only
            # touch already-built artifacts), functional via Python.
            run(
                *self._make_args("test-smoke", "test-integration"),
                cwd=self.repo_root,
            )
            self._run_functional_standalone()
        else:
            targets = self.targets if self.targets else ["test"]
            run(*self._make_args(*targets), cwd=self.repo_root)

    def _run_functional_standalone(self) -> None:
        """Run the standalone functional test using make_initrd.

        Creates an initrd bundling example.elf with system daemons via
        make_initrd, and a ramfs providing /tmp for test file output.
        """
        import tempfile

        binary = self.repo_root / "example.elf"
        if not binary.is_file():
            log.fatal(
                "example.elf not found.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z build` first.",
            )

        print("=== zlib functional tests ===")
        print("  Running example.elf via nanvixd standalone...")

        # Bundle example.elf + daemons into an initrd.
        initrd = make_initrd(
            self, "example.elf", InitRdArgs(app_args=["tmp/zlib_test"])
        )

        # Build a ramfs with /tmp for test file output.
        sysroot = self.config.get(CFG_SYSROOT, "")
        sysroot_path = Path(sysroot)
        mkramfs = sysroot_path / "bin" / "mkramfs.elf"

        try:
            with tempfile.TemporaryDirectory(prefix="nanvix_zlib_") as tmpdir:
                tmpdir_path = Path(tmpdir)
                ramfs_dir = tmpdir_path / "ramfs"
                ramfs_dir.mkdir()
                (ramfs_dir / "tmp").mkdir(exist_ok=True)
                ramfs_img = tmpdir_path / "rootfs.img"

                run(
                    str(mkramfs),
                    "-o",
                    str(ramfs_img),
                    str(ramfs_dir),
                )

                run(
                    str(sysroot_path / "bin" / "nanvixd.elf"),
                    "-bin-dir",
                    str(sysroot_path / "bin"),
                    "-ramfs",
                    str(ramfs_img),
                    "--",
                    str(initrd),
                    timeout=120,
                )
        finally:
            if initrd.exists():
                initrd.unlink()

        print("  PASS: example test standalone (exit code 0)")
        print("  PASS: zlib functional tests")
        print("=== All zlib tests PASSED ===")

    def _run_tests_windows(self) -> None:
        """Run tests natively on Windows.

        Only standalone mode is tested on Windows; multi-process and
        single-process require linuxd, which is Linux-only. Standalone
        test binaries are discovered in the repository root, where the
        Makefile emits the ELF outputs, rather than under `build/`.
        """
        if self.config.deployment_mode != "standalone":
            print(
                f"Skipping tests on Windows for mode '{self.config.deployment_mode}' (requires linuxd)."
            )
            return

        # --- standalone: full functional test via nanvixd.exe ---
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
                "nanvixd.exe not found.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z setup` first.",
            )
        if not mkramfs.is_file():
            log.fatal(
                "mkramfs.exe not found.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z setup` first.",
            )

        # The Makefile outputs ELFs directly to the repository root, not to a
        # build/ subdirectory.  Search the repo root first; fall back to build/
        # for forward-compatibility in case a future Makefile change moves them.
        test_allowlist = {"example.elf"}
        test_binaries: list[Path] = []
        for candidate in [self.repo_root, self.repo_root / "build"]:
            if candidate.is_dir():
                elfs = sorted(candidate.glob("*.elf"))
                found = [b for b in elfs if b.name in test_allowlist]
                for b in found:
                    if b.name not in {x.name for x in test_binaries}:
                        test_binaries.append(b)

        if not test_binaries:
            expected = ", ".join(sorted(test_allowlist))
            log.fatal(
                f"No allowlisted test binaries found. Expected: {expected}.",
                code=EXIT_MISSING_DEP,
                hint="Build the test binaries first (for example, run `./z build`) and then rerun `./z test`.",
            )

        import tempfile

        failed: list[str] = []
        for binary in test_binaries:
            name = binary.stem
            print(f"RUN  {name}...")
            # Bundle the test program in an initrd image.
            initrd = make_initrd(
                self, binary.name, InitRdArgs(app_args=["/tmp/zlib_test"])
            )
            # Build a ramfs image with a /tmp directory for test output.
            with tempfile.TemporaryDirectory(prefix=f"nanvix_{name}_") as tmpdir:
                tmpdir_path = Path(tmpdir)
                ramfs_dir = tmpdir_path / "ramfs"
                ramfs_dir.mkdir()
                (ramfs_dir / "tmp").mkdir(exist_ok=True)
                ramfs_img = tmpdir_path / f"rootfs_{name}.img"

                try:
                    run(
                        str(mkramfs),
                        "-o",
                        str(ramfs_img),
                        str(ramfs_dir),
                    )

                    run(
                        str(nanvixd),
                        "-bin-dir",
                        str(sysroot_path / "bin"),
                        "-ramfs",
                        str(ramfs_img),
                        "--",
                        str(initrd),
                        timeout=120,
                    )
                    print(f"OK   {name}")
                except SystemExit:
                    print(f"FAIL {name}")
                    failed.append(name)
                finally:
                    if initrd.exists():
                        initrd.unlink()

        if failed:
            msg = " ".join(failed)
            raise RuntimeError(f"{len(failed)} test(s) failed: {msg}")
        print(f"\t\t*** All {len(test_binaries)} tests PASSED ***")

    def release(self) -> None:
        """Package the zlib release tarball and verify it."""
        run(*self._make_args("package"), cwd=self.repo_root)
        run(*self._make_args("verify-package"), cwd=self.repo_root)

    def clean(self) -> None:
        """Remove build artifacts."""
        run(
            "make",
            "-f",
            ".nanvix/Makefile.nanvix",
            "clean",
            cwd=self.repo_root,
        )


if __name__ == "__main__":
    ZlibBuild.main()
