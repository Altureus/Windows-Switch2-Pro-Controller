# Third-party notices

This project bundles or builds on the following:

- **ViGEmClient.dll** (`procon2/vendor/`) — the user-mode client library for
  ViGEmBus, by Nefarius Software Solutions e.U. Licensed under the MIT License.
  It was extracted from the [`vgamepad`](https://pypi.org/project/vgamepad/) PyPI
  package (also MIT) via `procon2/vendor/_fetch_vigem.py`. The kernel-mode
  **ViGEmBus** driver is a **separate install** and is required at runtime:
  <https://github.com/nefarius/ViGEmBus>.

- **Switch 2 Pro Controller wake + haptic protocol** — reverse-engineered with
  help from HandHeldLegend's ProCon2Tool and the
  [`NSW2-controller-enabler`](https://github.com/ikz87/NSW2-controller-enabler)
  project. The haptic payloads in `procon2/haptics.py` are values observed from
  ProCon2Tool's own "play test haptic" output (kept within its safe range).

No third-party Python packages are used; everything else is pure `ctypes`
against the Win32 HID API, WinUSB, XInput, and ViGEmClient.
