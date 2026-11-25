# Contributing

Thanks for looking. This is a one-person project around a video series, so small and clear beats big and clever, and
I may be slow to answer.

- **Built one, or trying to?** Open an issue with the "Build question" template. Photos, your printer and filament,
  and the motor current at speed tell me more than anything else.
- **Found a bug?** Open an issue first for anything bigger than a typo. Say what you ran, what you expected and what
  happened.
- **Set up:** `py -m pip install -r requirements.txt` (use `python3` outside Windows).
- **Test:** `py -m pytest software/tests -q` must pass. The tests make no model calls and need no hardware: they use
  the simulator and `software/firmware/tools/mock_board.py`. Firmware logic goes in `software/firmware/lib/povcore`
  (plain C++14, no FreeRTOS) with a test in `software/firmware/test/`.
- **Anything that can light an LED goes through the current check.** The 2.6 A cap is a safety limit, not a
  preference. A change that adds a way to put pixels on the column has to cap it, on the PC and in the firmware.
- **Hardware changes:** say what you measured. A fit that worked on your printer is useful to the next person only
  with the numbers (bore, shaft, material, nozzle).
- **Nothing personal in the repo:** no Wi-Fi names or passwords, no addresses, no recordings of people. Pictures are
  real photos, real footage or simulator output.
- **Small pull requests**, one change each.

By contributing you agree that your work is released under this repository's licences: MIT for software, CERN-OHL-P
v2 for hardware design files, CC BY 4.0 for documentation ([LICENSING.md](LICENSING.md)).
