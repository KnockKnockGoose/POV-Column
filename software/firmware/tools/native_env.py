"""PlatformIO extra script for the `native` (host unit test) environment.

Puts the MinGW toolchain from the PlatformIO registry on PATH so SCons finds g++ and the test binaries find their DLLs,
whatever shell started pio (tools/pio.cmd does the same for interactive use). The toolchain was installed with
    pio pkg install -g -t platformio/toolchain-gccmingw32@1.50100.0      (GCC 5.1, i686, 96 MB)
PlatformIO's "native" platform ships no compiler of its own on Windows.
"""
import os

Import("env")  # noqa: F821  (SCons injects it)

pkgs = env.subst("$PROJECT_PACKAGES_DIR")
tc = os.path.join(pkgs, "toolchain-gccmingw32", "bin")
if os.path.isdir(tc):
    os.environ["PATH"] = tc + os.pathsep + os.environ.get("PATH", "")
    env.PrependENVPath("PATH", tc)
else:
    print("native_env.py: MinGW toolchain not found at", tc, "- install it with",
          "pio pkg install -g -t platformio/toolchain-gccmingw32@1.50100.0")
