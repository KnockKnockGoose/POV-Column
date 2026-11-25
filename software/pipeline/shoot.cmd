@echo off
rem POV column live demo: warm daemon + F9 watcher + step view window, one double-click before filming.
rem   shoot.cmd                          the real column (pov_config.json target)
rem   shoot.cmd --rehearse               a mock column on this PC (the board can stay off)
rem   shoot.cmd --model claude-opus-5-5  any pov_serve.py option passes through
rem See docs\2026-11-23-live-demo-pipeline.md. Ctrl+C in this window stops it.
title POV live demo
cd /d "%~dp0"
py -X utf8 pov_serve.py --shoot %*
if errorlevel 1 pause
