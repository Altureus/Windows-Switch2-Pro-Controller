# Third-party notices

This project bundles or builds on the following:

- **ViGEmClient.dll** (`procon2/vendor/`) — the user-mode client library for
  ViGEmBus, by Nefarius Software Solutions e.U. Licensed under the MIT License.
  It was extracted from the [`vgamepad`](https://pypi.org/project/vgamepad/) PyPI
  package (also MIT) via `procon2/vendor/_fetch_vigem.py`. The kernel-mode
  **ViGEmBus** driver is a **separate install** and is required at runtime:
  <https://github.com/nefarius/ViGEmBus>.

- **ViGEmBus driver installer** (`drivers/ViGEmBus_1.22.0_x64_x86_arm64.exe`) — the
  official ViGEmBus setup, v1.22.0, by Nefarius Software Solutions e.U., bundled
  unmodified for convenience so users can install the required kernel driver without
  a separate download. Source, newer versions, and license:
  <https://github.com/nefarius/ViGEmBus>.

- **Switch 2 Pro Controller wake + haptic protocol** — reverse-engineered with
  help from HandHeldLegend's ProCon2Tool and the
  [`NSW2-controller-enabler`](https://github.com/ikz87/NSW2-controller-enabler)
  project. The haptic payloads in `procon2/haptics.py` are values observed from
  ProCon2Tool's own "play test haptic" output (kept within its safe range).

- **Switch 2 Bluetooth LE protocol** (`procon2/ble_connect.py`,
  `procon2/ble_bridge.py`) — the BLE GATT characteristic UUIDs, the vendor
  command framing, the pairing/bonding handshake, and the input-report layout are
  adapted from [`CareyScott/switch2controllerpc`](https://github.com/CareyScott/switch2controllerpc),
  used and redistributed under the MIT License (see notice below).

- **bleak** — used only by the optional Bluetooth path (`ble_*.py`) for Windows
  BLE. MIT Licensed: <https://github.com/hbldh/bleak>. The wired USB path needs
  **no** Python packages.

The **core USB path** (`bridge.py` and friends) uses zero third-party Python
packages — pure `ctypes` against the Win32 HID API, WinUSB, XInput, and
ViGEmClient. Only the optional wireless path requires `bleak` (`pip install bleak`).

---

## MIT License — CareyScott/switch2controllerpc

```
MIT License

Copyright (c) 2026 Scott Carey

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
