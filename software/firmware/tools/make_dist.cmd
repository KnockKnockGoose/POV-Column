@echo off
rem Build phase0 and write the laptop flash images to dist\ (the desktop PC only; see tools\FLASH-FROM-LAPTOP.md).
rem   dist\phase0_0.3_merged.bin    bootloader 0x1000 + partitions 0x8000 + boot_app0 0xe000 + app 0x10000, flash at 0x0
rem   dist\phase0_0.3_firmware.bin  the app alone, for a later OTA
rem dist\*.bin is gitignored: built with src\wifi_secrets.h it carries the Wi-Fi credentials.
call "%~dp0pio.cmd" run -e phase0 || exit /b 1
cd /d "%~dp0.."
if not exist dist mkdir dist
C:\pio\penv\Scripts\esptool.exe --chip esp32 merge-bin -o dist\phase0_0.3_merged.bin --flash-mode dio --flash-freq 40m --flash-size 4MB ^
  0x1000 .pio\build\phase0\bootloader.bin 0x8000 .pio\build\phase0\partitions.bin ^
  0xe000 C:\pio\packages\framework-arduinoespressif32\tools\partitions\boot_app0.bin 0x10000 .pio\build\phase0\firmware.bin || exit /b 1
copy /y .pio\build\phase0\firmware.bin dist\phase0_0.3_firmware.bin >nul
echo dist\phase0_0.3_merged.bin + dist\phase0_0.3_firmware.bin written
