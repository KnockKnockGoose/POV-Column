@echo off
rem PlatformIO wrapper for the POV LED Column firmware (installed on the desktop PC 2026-11-03, see README.md).
rem   tools\pio.cmd run -e pov              build the column firmware
rem   tools\pio.cmd run -e pov -t upload    flash over USB (pigtail unplugged!)
rem   OTA: py tools\ota_flash.py --env pov  (streams, retries, verifies; docs\2026-11-13-ota-failure-review.md)
rem   tools\pio.cmd run -e phase0 -t upload    the bench bring-up sketch
rem   tools\pio.cmd test -e native          host unit tests
rem   tools\pio.cmd device monitor          serial console at 115200
rem Uses the PlatformIO Core venv C:\pio\pio-venv and keeps PlatformIO's home at C:\pio: the Arduino libs archive
rem has 200-character paths that overflow Windows' 260-character limit from C:\Users\<you>\.platformio.
rem Both C:\pio\pio-venv and C:\pio\penv (pioarduino's helper venv) are plain `python -m venv` venvs made from uv's
rem CPython at its REAL dir ...\uv\python\cpython-3.12.14-windows-x86_64-none. Not uv venvs: those point at the
rem cpython-3.12-... junction, which SSH sessions refuse to traverse ("untrusted mount point"), so pio failed over SSH
rem with "uv trampoline failed to spawn Python child process" (2026-11-13).
set "PLATFORMIO_CORE_DIR=C:\pio"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
rem ESP-IDF's idf_tools.py refuses to run inside an MSYS/MinGW shell (Git Bash exports MSYSTEM); clear it
set "MSYSTEM="
set "MSYS="
set "PATH=C:\pio\pio-venv\Scripts;C:\pio\packages\toolchain-gccmingw32\bin;%PATH%"
cd /d "%~dp0.."
pio %*
