# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Nanvix build script for zlib.

Usage:
    ./z setup      # Download Nanvix sysroot
    ./z build      # Cross-compile libz.a
    ./z test       # Run test suite (smoke + integration + functional)
    ./z release    # Package release tarball
    ./z clean      # Remove build artifacts
"""

from pathlib import Path

from nanvix_zutil import CFG_SYSROOT, CFG_TOOLCHAIN, ZScript, log, EXIT_BUILD_FAILURE

# zlib source files (matching upstream Makefile).
_OBJZ_SRCS = [
    "adler32.c", "crc32.c", "deflate.c", "infback.c", "inffast.c",
    "inflate.c", "inftrees.c", "trees.c", "zutil.c",
]
_OBJG_SRCS = [
    "compress.c", "uncompr.c", "gzclose.c", "gzlib.c", "gzread.c", "gzwrite.c",
]
_ALL_SRCS = _OBJZ_SRCS + _OBJG_SRCS
_CFLAGS = ["-O2", "-Wall", "-D_GNU_SOURCE", "-msse2", "-mfpmath=sse"]


class ZlibBuild(ZScript):
    """Build script for nanvix/zlib."""

    def _toolchain(self) -> Path:
        """Return the toolchain root, translated for Docker if active."""
        host = Path(self.config.get(CFG_TOOLCHAIN, "/opt/nanvix") or "/opt/nanvix")
        return self.translate_path(host) if self.docker else host

    def _sysroot(self) -> Path:
        """Return the sysroot path, translated for Docker if active."""
        sysroot_str = self.config.get(CFG_SYSROOT, "")
        if not sysroot_str:
            log.fatal(
                "Sysroot not configured — run './z setup' first.",
                code=EXIT_BUILD_FAILURE,
            )
        host = Path(sysroot_str)
        return self.translate_path(host) if self.docker else host

    def _cc(self) -> str:
        return f"{self._toolchain()}/bin/i686-nanvix-gcc"

    def _ar(self) -> str:
        return f"{self._toolchain()}/bin/i686-nanvix-ar"

    def _ranlib(self) -> str:
        return f"{self._toolchain()}/bin/i686-nanvix-ranlib"

    def _ldflags(self) -> list[str]:
        sysroot = self._sysroot()
        return [f"-T{sysroot}/lib/user.ld", "-static", "-Wl,-z,noexecstack"]

    def _nanvix_libs(self) -> list[str]:
        sysroot = self._sysroot()
        tc = self._toolchain()
        return [
            "-Wl,--start-group",
            f"{sysroot}/lib/libposix.a",
            f"{tc}/i686-nanvix/lib/libc.a",
            f"{tc}/i686-nanvix/lib/libm.a",
            "-Wl,--end-group",
        ]

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Cross-compile libz.a for Nanvix."""
        cc = self._cc()
        # Compile all source files.
        for src in _ALL_SRCS:
            obj = src.replace(".c", ".o")
            self.run(cc, *_CFLAGS, "-c", "-o", obj, src)
        # Archive into static library.
        objs = [s.replace(".c", ".o") for s in _ALL_SRCS]
        self.run(self._ar(), "rc", "libz.a", *objs)
        self.run(self._ranlib(), "libz.a")
        log.success("Built libz.a")

    def test(self) -> None:
        """Run the zlib test suite.

        Without targets, runs the full suite (smoke + integration + functional).
        Pass targets after ``--`` to select specific levels::

            ./z test -- smoke integration
        """
        targets = self.targets if self.targets else ["smoke", "integration", "functional"]
        if "smoke" in targets or "test-smoke" in targets:
            self._test_smoke()
        if "integration" in targets or "test-integration" in targets:
            self._test_integration()
        if "functional" in targets or "test-functional" in targets:
            self._test_functional()
        log.success("All zlib tests PASSED")

    def release(self) -> None:
        """Package the zlib release tarball."""
        machine = self.config.machine
        mode = self.config.deployment_mode
        mem = self.config.memory_size
        name = f"zlib-{machine}-{mode}-{mem}"
        dist = self.repo_root / "dist" / name
        # Create package layout.
        (dist / "sysroot" / "lib").mkdir(parents=True, exist_ok=True)
        (dist / "sysroot" / "include").mkdir(parents=True, exist_ok=True)
        (dist / "sysroot" / "bin").mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(self.repo_root / "libz.a", dist / "sysroot" / "lib" / "libz.a")
        shutil.copy2(self.repo_root / "zlib.h", dist / "sysroot" / "include" / "zlib.h")
        shutil.copy2(self.repo_root / "zconf.h", dist / "sysroot" / "include" / "zconf.h")
        for prog in ["example.elf", "minigzip.elf"]:
            src = self.repo_root / prog
            if src.exists():
                shutil.copy2(src, dist / "sysroot" / "bin" / prog)
        # Create tarball.
        tarball = self.repo_root / "dist" / f"{name}.tar.bz2"
        self.run("tar", "-cjf", str(tarball), "-C", str(dist), "sysroot", docker=False)
        # Verify.
        self.run("tar", "tjf", str(tarball), docker=False)
        log.success(f"Package: {tarball}")

    def clean(self) -> None:
        """Remove build artifacts."""
        patterns = ["*.o", "*.a", "*.elf"]
        for pattern in patterns:
            for f in self.repo_root.glob(pattern):
                f.unlink()
        for f in (self.repo_root / "test").glob("*.o"):
            f.unlink()
        dist = self.repo_root / "dist"
        if dist.exists():
            import shutil
            shutil.rmtree(dist)
        log.success("Cleaned build artifacts")

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def _test_smoke(self) -> None:
        log.info("=== zlib smoke tests ===")
        libz = self.repo_root / "libz.a"
        if not libz.exists():
            log.fatal("libz.a not found", code=EXIT_BUILD_FAILURE)
        if libz.stat().st_size < 1000:
            log.fatal("libz.a too small", code=EXIT_BUILD_FAILURE)
        for hdr in ["zlib.h", "zconf.h"]:
            if not (self.repo_root / hdr).exists():
                log.fatal(f"{hdr} not found", code=EXIT_BUILD_FAILURE)
        log.success("PASS: zlib smoke tests")

    def _test_integration(self) -> None:
        log.info("=== zlib integration tests ===")
        cc = self._cc()
        # Build test programs.
        for prog in ["example", "minigzip"]:
            self.run(cc, *_CFLAGS, "-I.", "-c", "-o", f"test/{prog}.o", f"test/{prog}.c")
            self.run(
                cc, *_CFLAGS, *self._ldflags(),
                "-o", f"{prog}.elf", f"test/{prog}.o",
                "-L.", "-lz", *self._nanvix_libs(),
            )
        # Verify binaries exist.
        for prog in ["example.elf", "minigzip.elf"]:
            if not (self.repo_root / prog).exists():
                log.fatal(f"{prog} not built", code=EXIT_BUILD_FAILURE)
        log.success("PASS: zlib integration tests")

    def _test_functional(self) -> None:
        log.info("=== zlib functional tests ===")
        sysroot = self._sysroot()
        binary = self.translate_path(
            (self.repo_root / "example.elf").resolve()
        )
        if self.config.deployment_mode == "standalone":
            # Standalone mode: use ramfs.
            import shlex
            workspace = shlex.quote(str(self.translate_path(self.repo_root.resolve())))
            sr = shlex.quote(str(sysroot))
            self.run(
                "sh", "-c",
                f"mkdir -p /tmp/nanvix-ramfs && "
                f"cp {workspace}/example.elf /tmp/nanvix-ramfs/ && "
                f"{sr}/bin/mkramfs.elf -o /tmp/rootfs.img /tmp/nanvix-ramfs/ && "
                f"timeout --foreground 120 {sr}/bin/nanvixd.elf "
                f"-bin-dir {sr}/bin -ramfs /tmp/rootfs.img "
                f"-- ./example.elf /tmp/zlib_test",
                kvm=True,
            )
        else:
            self.run(
                "timeout", "--foreground", "120",
                f"{sysroot}/bin/nanvixd.elf",
                "--", str(binary), "/tmp/zlib_test",
                kvm=True,
            )
        log.success("PASS: zlib functional tests")


if __name__ == "__main__":
    ZlibBuild.main()
